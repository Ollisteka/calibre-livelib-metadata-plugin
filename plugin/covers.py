from urllib.request import Request, urlopen
from .constants import USER_AGENT
from .constants import BASE_URL
from .constants import BETA_BASE_URL
from .constants import IDENTIFIER_TYPE_FANTLAB
from .constants import IDENTIFIER_TYPE_LITRES
from .constants import IDENTIFIER_TYPE_LIVELIB
from calibre import as_unicode
from queue import Empty
from queue import Queue
from urllib.parse import quote
import re


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

    def __init__(self, cached_cover, identify, litres, livelib, fantlab):
        self.cached_cover = cached_cover
        self.identify = identify
        self.litres = litres
        self.livelib = livelib
        self.fantlab = fantlab

    def get_cached_cover_url(self, identifiers):
        litres_id = (identifiers or {}).get(IDENTIFIER_TYPE_LITRES)
        if litres_id:
            return self.cached_cover(litres_id)
        livelib_id = (identifiers or {}).get(IDENTIFIER_TYPE_LIVELIB)
        if livelib_id:
            return self.cached_cover(livelib_id)
        fantlab_id = (identifiers or {}).get(IDENTIFIER_TYPE_FANTLAB)
        if fantlab_id:
            return self.cached_cover(fantlab_id)
        return None

    def find_cover_url_direct(self, log, title=None, authors=None, timeout=30):
        for candidate in self.litres.search_litres(log, title, authors, timeout):
            if candidate.get('cover_url'):
                return candidate['cover_url']
        query = ' '.join([title or ''] + list(authors or [])).strip()
        if query:
            for url in (
                    BETA_BASE_URL + '/search?q=' + quote(query),
                    BASE_URL + '/find/' + quote(query),
            ):
                try:
                    for candidate in self.livelib.search_page(url, title, authors, timeout):
                        if candidate.get('cover_url'):
                            return candidate['cover_url']
                except Exception as err:
                    log.exception('Direct LiveLib cover search failed: %s' % as_unicode(err))
        for candidate in self.fantlab.search_fantlab(log, title, authors, timeout):
            if candidate.get('cover_url'):
                return candidate['cover_url']
        return None

    def find_all_cover_urls(self, log, result_queue_abort, title, authors, identifiers, timeout):
        """Collect cover URLs from every matched source, ordered by relevance."""
        urls = []
        seen = set()

        def add(url):
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        add(self.get_cached_cover_url(identifiers))
        if title or authors:
            q = Queue()
            self.identify(log, q, result_queue_abort, title=title, authors=authors,
                          identifiers=identifiers, timeout=timeout)
            # Drain the whole queue so covers from every matched source (LitRes,
            # LiveLib, FantLab) are gathered, not just the single top-scoring hit.
            while True:
                try:
                    mi = q.get_nowait()
                except Empty:
                    break
                add(self.get_cached_cover_url(mi.identifiers))
        if not urls and (title or authors):
            add(self.find_cover_url_direct(log, title=title, authors=authors, timeout=timeout))
        return urls


def expand_cover_urls(urls):
    candidates = []
    seen = set()
    for url in urls:
        for candidate in livelib_cover_candidates(url):
            if candidate and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
    return candidates


def attach_cover_data(mi, cover_url, timeout):
    if not cover_url:
        return
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Referer': BASE_URL + '/',
    }
    raw = None
    downloaded_url = cover_url
    for candidate_url in livelib_cover_candidates(cover_url):
        try:
            raw = urlopen(Request(candidate_url, headers=headers), timeout=timeout).read()
            downloaded_url = candidate_url
            break
        except Exception:
            continue
    if raw is None:
        raw = urlopen(Request(cover_url, headers=headers), timeout=timeout).read()
    fmt = 'jpeg'
    lowered = downloaded_url.lower()
    if lowered.endswith('.png'):
        fmt = 'png'
    elif lowered.endswith('.webp'):
        fmt = 'webp'
    mi.cover_data = (fmt, raw)
    mi.has_cover = True
