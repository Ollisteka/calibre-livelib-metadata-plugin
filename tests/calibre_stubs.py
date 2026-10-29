"""Small storage-only stand-ins; these do not validate Calibre's behavior."""
import sys
from types import ModuleType


class Metadata:
    def __init__(self, title, authors):
        self.title = title
        self.authors = authors
        self.identifiers = {}
        self.language = self.comments = self.publisher = self.pubdate = None
        self.rating = self.isbn = None
        self.tags = []
        self.has_cover = False

    def set_identifier(self, key, value):
        self.identifiers[key] = value


class Source:
    def __init__(self):
        self._covers = {}

    def cache_identifier_to_cover_url(self, identifier, url):
        self._covers[identifier] = url

    def cached_identifier_to_cover_url(self, identifier):
        return self._covers.get(identifier)

    def download_multiple_covers(self, *args, **kwargs):
        raise AssertionError('Replace the Calibre downloader in this test')


def install():
    names = ('calibre', 'calibre.ebooks', 'calibre.ebooks.metadata',
             'calibre.ebooks.metadata.book', 'calibre.ebooks.metadata.book.base',
             'calibre.ebooks.metadata.sources', 'calibre.ebooks.metadata.sources.base')
    for name in names:
        sys.modules[name] = ModuleType(name)
    sys.modules['calibre'].as_unicode = str
    # No ISBN validation is exercised in this suite; do not duplicate Calibre's algorithm.
    def unsupported_isbn(value):
        raise AssertionError('ISBN validation requires a Calibre integration test')
    sys.modules['calibre.ebooks.metadata'].check_isbn = unsupported_isbn
    sys.modules['calibre.ebooks.metadata.book.base'].Metadata = Metadata
    sys.modules['calibre.ebooks.metadata.sources.base'].Source = Source
