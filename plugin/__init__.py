from .constants import IDENTIFIER_TYPE_FANTLAB
from .constants import IDENTIFIER_TYPE_ISBN
from .constants import IDENTIFIER_TYPE_LITRES
from .constants import IDENTIFIER_TYPE_LIVELIB
from .covers import CoverService
from .covers import expand_cover_urls
from .identifiers import get_book_url
from .identifiers import get_book_url_name
from .identifiers import id_from_url
from .identify import identify
from .providers.fantlab import FantlabProvider
from .providers.litres import LitresProvider
from .providers.livelib.provider import LiveLibProvider
from .transport import Transport
from calibre.ebooks.metadata.sources.base import Source


__license__ = 'GPL-3.0-only'
__copyright__ = '2026, Emin Ganbarov and contributors'

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
        self.litres = LitresProvider(self.transport, self.cache_identifier_to_cover_url)
        self.livelib = LiveLibProvider(self.transport, self.cache_identifier_to_cover_url)
        self.fantlab = FantlabProvider(self.transport, self.cache_identifier_to_cover_url)
        self.covers = CoverService(
            self.cached_identifier_to_cover_url,
            lambda *args, **kwargs: self.identify(*args, **kwargs),
            self.litres, self.livelib, self.fantlab)

    def get_book_url(self, identifiers):
        return get_book_url(identifiers)

    def get_book_url_name(self, idtype, idval, url):
        return get_book_url_name(idtype, self.name)

    def id_from_url(self, url):
        return id_from_url(url)

    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers=None, timeout=30):
        return identify(self.litres, self.livelib, self.fantlab,
                        self.cache_identifier_to_cover_url, log, result_queue,
                        abort, title, authors, identifiers, timeout)

    def get_cached_cover_url(self, identifiers):
        return self.covers.get_cached_cover_url(identifiers)

    def download_cover(self, log, result_queue, abort, title=None, authors=None,
                       identifiers=None, timeout=30, get_best_cover=False):
        urls = self.covers.find_all_cover_urls(
            log, abort, title, authors, identifiers or {}, timeout)
        candidates = expand_cover_urls(urls)
        if candidates:
            self.download_multiple_covers(title, authors, candidates, get_best_cover,
                                          timeout, result_queue, abort, log,
                                          prefs_name=None)
