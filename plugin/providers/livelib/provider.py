from ...constants import IDENTIFIER_TYPE_LIVELIB
from ...identifiers import livelib_beta_url
from ...identifiers import livelib_id_from_url
from ...providers.livelib.formatting import append_edition_details
from ...providers.livelib.parsers import extract_livelib_json
from ...providers.livelib.parsers import extract_livelib_page_details
from ...providers.livelib.parsers import parse_search_results
from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from datetime import datetime
from html import escape
import re


class LiveLibProvider:
    """LiveLib candidates carry source, score, url and author (a single string)."""

    def __init__(self, transport, cache_cover):
        self.transport = transport
        self.cache_cover = cache_cover

    def metadata_from_search_candidate(self, candidate):
        title = candidate.get('title') or ''
        author = candidate.get('author') or 'Unknown'
        if not title:
            return None
        mi = Metadata(title, [author])
        mi.language = 'rus'
        livelib_id = livelib_id_from_url(candidate.get('url'))
        if livelib_id:
            mi.set_identifier(IDENTIFIER_TYPE_LIVELIB, livelib_id)
        # Do not overwrite an existing annotation with a bare source link.
        if candidate.get('summary'):
            mi.comments = '<p>%s</p>' % as_unicode(candidate.get('summary')).strip()
        try:
            if candidate.get('rating'):
                mi.rating = float(candidate['rating']) * 2
        except Exception:
            pass
        cover_url = candidate.get('cover_url')
        if cover_url and livelib_id:
            self.cache_cover(livelib_id, cover_url)
        return mi

    def fetch_book(self, log, url, timeout):
        url = livelib_beta_url(url)
        raw = self.transport.fetch_url(url, timeout)
        return self.metadata_from_page(raw, url)

    def metadata_from_page(self, raw, url):
        data = extract_livelib_json(raw)
        if not data:
            return None

        author_data = data.get('author') or {}
        author_name = author_data.get('name') if isinstance(author_data, dict) else author_data
        title = data.get('name') or ''
        authors = [author_name] if author_name else ['Unknown']
        mi = Metadata(title, authors)
        mi.language = 'rus'

        livelib_id = livelib_id_from_url(url) or livelib_id_from_url(data.get('url'))
        if livelib_id:
            mi.set_identifier(IDENTIFIER_TYPE_LIVELIB, livelib_id)

        details = extract_livelib_page_details(raw)

        isbn = check_isbn(data.get('isbn') or details.get('isbn'))
        if isbn:
            mi.isbn = isbn

        publisher = details.get('publisher')
        if not publisher:
            publisher_data = data.get('publisher') or {}
            if isinstance(publisher_data, dict):
                publisher = publisher_data.get('name')
            elif publisher_data:
                publisher = as_unicode(publisher_data)
        if publisher:
            mi.publisher = publisher

        year = details.get('year')
        if year:
            match = re.search(r'\d{4}', year)
            if match:
                try:
                    mi.pubdate = datetime(int(match.group(0)), 1, 1)
                except Exception:
                    pass

        description = data.get('description')
        comments = None
        if description:
            comments = '<p>%s</p>' % escape(description).replace('\n', '<br/>')

        genres = data.get('genre') or []
        if isinstance(genres, str):
            genres = [genres]
        mi.tags = [g for g in genres if g]

        rating = ((data.get('aggregateRating') or {}).get('ratingValue'))
        rating_count = ((data.get('aggregateRating') or {}).get('ratingCount'))
        try:
            # Calibre ratings are on a 0..10 scale.
            mi.rating = float(rating) * 2
        except Exception:
            pass

        mi.comments = append_edition_details(comments, details, rating_count=rating_count)

        image = data.get('image')
        if image and livelib_id:
            self.cache_cover(livelib_id, image)
            mi.has_cover = True

        return mi

    def search_page(self, url, title, authors, timeout, log=None):
        try:
            raw = self.transport.fetch_url(url, timeout)
        except Exception as err:
            if log is None:
                raise
            log.exception('LiveLib search failed: %s' % as_unicode(err))
            return []
        # Parsing errors have always propagated during identify; only transport
        # errors are recoverable here. Direct cover lookup catches both outside.
        return parse_search_results(raw, title, authors) if raw else []
