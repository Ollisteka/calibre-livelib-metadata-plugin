from .constants import BASE_URL
from .constants import BETA_BASE_URL
from calibre import as_unicode
from queue import Empty
from queue import Queue
from urllib.parse import quote
import re
from .config import SOURCE_NAMES
from time import monotonic


def livelib_original_cover_url(url):
    if not url:
        return None
    match = re.match(r'(https?://s\d+\.livelib\.ru/boocover/\d+)/(?:\d+x\d+)/(.*?)/([^/?#]+)$', url)
    if not match:
        return None
    base, shard, filename = match.groups()
    filename = re.sub(r'\.(?:jpg|jpeg|png|webp)$', '.jpeg', filename, flags=re.IGNORECASE)
    return '%s/o/%s/%s' % (base, shard, filename)


def livelib_cover_candidates(url):
    urls = []
    original = livelib_original_cover_url(url)
    if original:
        urls.append(original)
    if url and url not in urls:
        urls.append(url)
    return urls


class CoverService:
    """Per-instance cache access and collection, with an injected identify callback."""

    def __init__(self, cached_cover, identify, litres, livelib, fantlab, enabled_sources=None):
        self.cached_cover = cached_cover
        self.identify = identify
        self.litres = litres
        self.livelib = livelib
        self.fantlab = fantlab
        self.enabled_sources = enabled_sources or (lambda: frozenset(SOURCE_NAMES))

    def get_cached_cover_url(self, identifiers):
        return next(iter(self.get_cached_cover_urls(identifiers)), None)

    def get_cached_cover_urls(self, identifiers, enabled=None):
        enabled = self.enabled_sources() if enabled is None else enabled
        urls = []
        for kind in SOURCE_NAMES:
            identifier = (identifiers or {}).get(kind)
            if kind in enabled and identifier:
                url = self.cached_cover(kind, identifier)
                if url and url not in urls:
                    urls.append(url)
        return urls

    def find_cover_url_direct(self, log, title=None, authors=None, timeout=30, enabled=None, abort=None):
        enabled = self.enabled_sources() if enabled is None else enabled
        deadline = monotonic() + timeout

        def stopped():
            return (abort is not None and abort.is_set()) or monotonic() >= deadline

        if stopped():
            return None
        if 'litres' in enabled:
            try:
                for candidate in self.litres.search_litres(log, title, authors, max(0.001, deadline - monotonic()), abort=abort):
                    if candidate.get('cover_url'):
                        return candidate['cover_url']
            except Exception as err:
                log.exception('Direct LitRes cover search failed: %s' % as_unicode(err))
        query = ' '.join([title or ''] + list(authors or [])).strip()
        if query and 'livelib' in enabled and not stopped():
            for url in (
                    BETA_BASE_URL + '/search?q=' + quote(query),
                    BASE_URL + '/find/' + quote(query),
            ):
                if stopped():
                    return None
                try:
                    for candidate in self.livelib.search_page(url, title, authors, max(0.001, deadline - monotonic())):
                        if candidate.get('cover_url'):
                            return candidate['cover_url']
                except Exception as err:
                    log.exception('Direct LiveLib cover search failed: %s' % as_unicode(err))
        if 'fantlab' in enabled and not stopped():
            try:
                for candidate in self.fantlab.search_fantlab(log, title, authors, max(0.001, deadline - monotonic())):
                    if candidate.get('cover_url'):
                        return candidate['cover_url']
            except Exception as err:
                log.exception('Direct FantLab cover search failed: %s' % as_unicode(err))
        return None

    def find_all_cover_urls(self, log, abort, title, authors, identifiers, timeout):
        """Collect cached covers of returned candidates, ordered by relevance."""
        if abort.is_set():
            return []
        urls = []
        seen = set()
        enabled = self.enabled_sources()
        deadline = monotonic() + timeout
        if not enabled or abort.is_set():
            return []

        def add(url):
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        for url in self.get_cached_cover_urls(identifiers, enabled):
            add(url)
        if title or authors or any((identifiers or {}).get(kind) for kind in enabled):
            q = Queue()
            self.identify(log, q, abort, title=title, authors=authors,
                          identifiers=identifiers, timeout=timeout, enabled=enabled)
            # Drain the whole queue so covers from every matched source (LitRes,
            # LiveLib, FantLab) are gathered, not just the single top-scoring hit.
            while True:
                try:
                    mi = q.get_nowait()
                except Empty:
                    break
                for url in self.get_cached_cover_urls(mi.identifiers, enabled):
                    add(url)
        remaining = deadline - monotonic()
        if not urls and (title or authors) and remaining > 0 and not abort.is_set():
            add(self.find_cover_url_direct(log, title=title, authors=authors, timeout=remaining,
                                           enabled=enabled, abort=abort))
        return [] if abort.is_set() else urls


def expand_cover_urls(urls):
    candidates = []
    seen = set()
    for url in urls:
        for candidate in livelib_cover_candidates(url):
            if candidate and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
    return candidates
