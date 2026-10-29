from __future__ import absolute_import, division, print_function, unicode_literals


from types import SimpleNamespace


__license__ = 'GPL-3.0-only'


__copyright__ = '2026, Emin Ganbarov and contributors'


import json


import re


from datetime import datetime


from html import escape, unescape


from queue import Empty, Queue


from urllib.parse import quote, urlencode, urljoin, urlsplit


from urllib.request import Request, urlopen


from lxml import html


from calibre import as_unicode


from calibre.ebooks.metadata import check_isbn


from calibre.ebooks.metadata.book.base import Metadata


from calibre.ebooks.metadata.sources.base import Source


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


from .constants import BASE_URL


from .constants import BETA_BASE_URL


from .constants import FANTLAB_BASE_URL


from .constants import FANTLAB_API_BASE_URL


from .constants import LITRES_API_BASE


from .constants import LITRES_WEB_BASE


from .constants import IDENTIFIER_TYPE_LITRES


from .constants import IDENTIFIER_TYPE_LIVELIB


from .constants import IDENTIFIER_TYPE_FANTLAB


from .constants import IDENTIFIER_TYPE_ISBN


from .constants import FANTLAB_IDENTIFIER_PATTERN


from .constants import USER_AGENT


from .matching import norm


from .matching import score_match


from .matching import title_match_enough


from .identifiers import livelib_id_from_url


from .identifiers import fantlab_identifier_from_url


from .identifiers import livelib_beta_url


from .identifiers import get_book_url


from .identifiers import id_from_url


from .identifiers import get_book_url_name


from .html_utils import clean_html


from .html_utils import safe_html_fromstring


from .html_utils import extract_balanced_json


from .html_utils import compact_page_text


from .html_utils import extract_between


from .transport import Transport


from .providers.livelib.formatting import append_edition_details


from .providers.litres import LitresProvider


from .providers.fantlab import FantlabProvider


from .providers.livelib.parsers import decode_next_payload


from .providers.livelib.parsers import source_rating


from .providers.livelib.parsers import extract_livelib_json


from .providers.livelib.parsers import extract_livelib_page_details


from .providers.livelib.parsers import parse_beta_search_payload


from .providers.livelib.parsers import parse_search_results


from .providers.livelib.provider import LiveLibProvider


from .identify import STRONG_MATCH_SCORE


from .identify import identify


class LiveLibMetadata(Source):
    name = 'LiveLib Metadata'
    description = 'Downloads Russian metadata and covers from LitRes, LiveLib, and FantLab'
    author = 'OpenAI Codex for Emin'
    version = (0, 3, 3)
    minimum_calibre_version = (6, 0, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset([
        'title', 'authors',
        'identifier:' + IDENTIFIER_TYPE_LITRES,
        'identifier:' + IDENTIFIER_TYPE_LIVELIB,
        'identifier:' + IDENTIFIER_TYPE_FANTLAB,
        'identifier:' + IDENTIFIER_TYPE_ISBN,
        'comments', 'publisher', 'pubdate', 'tags', 'rating', 'languages'
    ])
    has_html_comments = True
    supports_gzip_transfer_encoding = True
    can_get_multiple_covers = True


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = Transport()
        provider_transport = SimpleNamespace(fetch_url=lambda *a: self.fetch_url(*a), fetch_json=lambda *a: self.fetch_json(*a))
        self.litres = LitresProvider(provider_transport, self.cache_identifier_to_cover_url)
        self.fantlab = FantlabProvider(provider_transport, self.cache_identifier_to_cover_url)
        self.livelib = LiveLibProvider(provider_transport, self.cache_identifier_to_cover_url)


    def fetch_url(self, *args, **kwargs):
        return self.transport.fetch_url(*args, **kwargs)


    def fetch_json(self, *args, **kwargs):
        return self.transport.fetch_json(*args, **kwargs)


    def absolutize_litres_cover(self, *args, **kwargs):
        return self.litres.absolutize_litres_cover(*args, **kwargs)


    def attach_cover_data(self, mi, cover_url, timeout):
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


    def get_book_url(self, *args, **kwargs):
        return get_book_url(*args, **kwargs)


    def get_book_url_name(self, idtype, idval, url):
        return get_book_url_name(idtype, self.name)


    def id_from_url(self, *args, **kwargs):
        return id_from_url(*args, **kwargs)


    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers=None, timeout=30):
        return identify(self.litres, self.livelib, self.fantlab, self.cache_identifier_to_cover_url, log, result_queue, abort, title, authors, identifiers, timeout)


    def search_litres(self, *args, **kwargs):
        return self.litres.search_litres(*args, **kwargs)


    def metadata_from_litres_candidate(self, *args, **kwargs):
        return self.litres.metadata_from_litres_candidate(*args, **kwargs)


    def fetch_litres_book(self, *args, **kwargs):
        return self.litres.fetch_litres_book(*args, **kwargs)


    def parse_beta_search_payload(self, *args, **kwargs):
        return parse_beta_search_payload(*args, **kwargs)


    def parse_search_results(self, *args, **kwargs):
        return parse_search_results(*args, **kwargs)


    def search_fantlab(self, *args, **kwargs):
        return self.fantlab.search_fantlab(*args, **kwargs)


    def metadata_from_search_candidate(self, *args, **kwargs):
        return self.livelib.metadata_from_search_candidate(*args, **kwargs)


    def metadata_from_fantlab_candidate(self, *args, **kwargs):
        return self.fantlab.metadata_from_fantlab_candidate(*args, **kwargs)


    def fetch_book(self, *args, **kwargs):
        return self.livelib.fetch_book(*args, **kwargs)


    def get_cached_cover_url(self, identifiers):
        litres_id = (identifiers or {}).get(IDENTIFIER_TYPE_LITRES)
        if litres_id:
            return self.cached_identifier_to_cover_url(litres_id)
        livelib_id = (identifiers or {}).get(IDENTIFIER_TYPE_LIVELIB)
        if livelib_id:
            return self.cached_identifier_to_cover_url(livelib_id)
        fantlab_id = (identifiers or {}).get(IDENTIFIER_TYPE_FANTLAB)
        if fantlab_id:
            return self.cached_identifier_to_cover_url(fantlab_id)
        return None


    def find_cover_url_direct(self, log, title=None, authors=None, timeout=30):
        for candidate in self.search_litres(log, title, authors, timeout):
            if candidate.get('cover_url'):
                return candidate['cover_url']
        query = ' '.join([title or ''] + list(authors or [])).strip()
        if query:
            for url in (
                    BETA_BASE_URL + '/search?q=' + quote(query),
                    BASE_URL + '/find/' + quote(query),
            ):
                try:
                    raw = self.fetch_url(url, timeout)
                    for candidate in self.parse_search_results(raw, title, authors):
                        if candidate.get('cover_url'):
                            return candidate['cover_url']
                except Exception as err:
                    log.exception('Direct LiveLib cover search failed: %s' % as_unicode(err))
        for candidate in self.search_fantlab(log, title, authors, timeout):
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


    def download_cover(self, log, result_queue, abort, title=None, authors=None,
                       identifiers=None, timeout=30, get_best_cover=False):
        identifiers = identifiers or {}
        urls = self.find_all_cover_urls(log, abort, title, authors, identifiers, timeout)
        if not urls:
            return
        # Expand each source URL into its resolution variants (e.g. the LiveLib
        # original /o/...jpeg plus the preview) and download them all together.
        candidates = []
        seen = set()
        for url in urls:
            for candidate in livelib_cover_candidates(url):
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
        if candidates:
            self.download_multiple_covers(title, authors, candidates, get_best_cover,
                                          timeout, result_queue, abort, log,
                                          prefs_name=None)
