import sys as _sys


def _discard_cached_submodules():
    # Calibre reloads only this entry module when installing a replacement ZIP.
    # Re-import our own submodules from that ZIP rather than mixing releases.
    prefix = __name__ + '.'
    for name in tuple(_sys.modules):
        if name.startswith(prefix):
            del _sys.modules[name]


_discard_cached_submodules()


from .constants import IDENTIFIER_TYPE_FANTLAB
from .constants import IDENTIFIER_TYPE_ISBN
from .constants import IDENTIFIER_TYPE_LITRES
from .constants import IDENTIFIER_TYPE_LIVELIB
from .config import SOURCE_OPTIONS
from .config import PERSONAL_OPTIONS
from .config import enabled_sources
from .covers import CoverService
from .covers import expand_cover_urls
from .identifiers import get_book_url
from .identifiers import get_book_urls
from .identifiers import get_book_url_name
from .identifiers import id_from_url
from .identify import identify
from .providers.fantlab import FantlabProvider
from .providers.litres import LitresProvider
from .providers.livelib.provider import LiveLibProvider
from .providers.livelib.reading import ReadingHistory
from .transport import Transport
from calibre.ebooks.metadata.sources.base import Source
from time import monotonic


__license__ = 'GPL-3.0-only'
__copyright__ = '2026, Emin Ganbarov and contributors'

class LiveLibMetadata(Source):
    name = 'LiveLib Metadata'
    description = 'Downloads Russian metadata and covers from LitRes, LiveLib, and FantLab'
    author = 'OpenAI Codex for Emin'
    version = (0, 5, 1)
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
    options = SOURCE_OPTIONS + PERSONAL_OPTIONS
    config_help_message = (
        'Выберите источники метаданных и обложек. Если отключить все источники, '
        'плагин не будет обращаться к сервисам. Сохранённые ID остаются в книге.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = Transport()
        self.litres = LitresProvider(self.transport, self._cover_cache_writer('litres'))
        self.livelib = LiveLibProvider(self.transport, self._cover_cache_writer('livelib'))
        self.reading = ReadingHistory(self.transport)
        self.fantlab = FantlabProvider(self.transport, self._cover_cache_writer('fantlab'))
        self.covers = CoverService(
            self.cached_source_cover_url,
            lambda *args, **kwargs: self.identify(*args, include_personal=False, **kwargs),
            self.litres, self.livelib, self.fantlab,
            lambda: enabled_sources(self.prefs))

    def _cover_cache_writer(self, source):
        return lambda identifier, url: self.cache_identifier_to_cover_url(
            source + ':' + str(identifier), url)

    def cached_source_cover_url(self, source, identifier):
        return self.cached_identifier_to_cover_url(source + ':' + str(identifier))

    def get_book_url(self, identifiers):
        return get_book_url(identifiers)

    def get_book_urls(self, identifiers):
        return get_book_urls(identifiers)

    def get_book_url_name(self, idtype, idval, url):
        return get_book_url_name(idtype, self.name)

    def id_from_url(self, url):
        return id_from_url(url)

    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers=None, timeout=30, enabled=None, include_personal=True):
        enabled = enabled_sources(self.prefs) if enabled is None else enabled
        username = (self.prefs['livelib_username'] or '').strip()
        enrich_personal = None
        if include_personal and username and 'livelib' in enabled:
            enrich_personal = lambda results, remaining: self.reading.enrich(
                results, username, log, abort, remaining)
        return identify(self.litres, self.livelib, self.fantlab,
                        log, result_queue,
                        abort, title, authors, identifiers, timeout,
                        enabled, enrich_personal=enrich_personal,
                        fallback_public_rating=self.prefs['livelib_rating_fallback'] == 'public')

    def get_cached_cover_url(self, identifiers):
        return self.covers.get_cached_cover_url(identifiers)

    def download_cover(self, log, result_queue, abort, title=None, authors=None,
                       identifiers=None, timeout=30, get_best_cover=False):
        deadline = monotonic() + timeout
        urls = self.covers.find_all_cover_urls(
            log, abort, title, authors, identifiers or {}, timeout)
        candidates = expand_cover_urls(urls)
        remaining = deadline - monotonic()
        if candidates and remaining > 0 and not abort.is_set():
            self.download_multiple_covers(title, authors, candidates, get_best_cover,
                                          remaining, result_queue, abort, log,
                                          prefs_name=None)
