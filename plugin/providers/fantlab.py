from ..constants import FANTLAB_API_BASE_URL
from ..constants import FANTLAB_BASE_URL
from ..constants import IDENTIFIER_TYPE_FANTLAB
from ..identifiers import fantlab_identifier_from_url
from ..matching import score_match
from calibre import as_unicode
from calibre.ebooks.metadata.book.base import Metadata
from urllib.parse import quote
import json
import re
from urllib.parse import urljoin


class FantlabProvider:
    """FantLab candidates carry authors, numeric id and a resource-path identifier."""

    def __init__(self, transport, cache_cover):
        self.transport = transport
        self.cache_cover = cache_cover

    def fetch_book(self, log, identifier, timeout):
        # The documented mini-card endpoint supports both works and editions.
        match = re.fullmatch(r'(work|edition)(\d+)', as_unicode(identifier))
        if not match:
            raise ValueError('Unsupported FantLab resource identifier: ' + as_unicode(identifier))
        kind, number = match.groups()
        parameter, block = ('w', 'works') if kind == 'work' else ('e', 'editions')
        url = FANTLAB_API_BASE_URL + '/search-ids?' + parameter + '=' + number
        log.info('FantLab direct lookup: ' + url)
        payload = self.transport.fetch_fantlab_json(url, timeout)
        for item in payload.get(block) or []:
            if as_unicode(item.get('id')) != number:
                continue
            return self.metadata_from_fantlab_candidate({
                'identifier': identifier, 'title': item.get('name') or '',
                'authors': [a['name'] for a in (item.get('creators') or {}).get('authors', [])
                            if a.get('name')],
                'comments': item.get('description'),
                'rating': (item.get('stat') or {}).get('rating'),
                'cover_url': urljoin(FANTLAB_API_BASE_URL, item['image']) if item.get('image') else None,
                'tags': [item['name_type']] if item.get('name_type') else [],
            })
        return None

    def search_fantlab(self, log, query_title, query_authors, timeout):
        query = ' '.join([query_title or ''] + list(query_authors or [])).strip()
        if not query:
            return []
        url = FANTLAB_API_BASE_URL + '/search-txt?q=' + quote(query)
        log.info('FantLab fallback search: ' + url)
        try:
            payload = self.transport.fetch_fantlab_json(url, timeout)
        except Exception as err:
            log.exception('FantLab search failed: %s' % as_unicode(err))
            return []

        candidates = []
        for item in payload.get('works') or []:
            fantlab_identifier = fantlab_identifier_from_url(item.get('url'))
            title = item.get('name') or ''
            author_names = [
                a.get('name') for a in ((item.get('creators') or {}).get('authors') or [])
                if a.get('name')
            ]
            author = ', '.join(author_names)
            score = score_match(query_title, query_authors, title, author)
            if score < 50:
                continue
            if item.get('type') != 'work':
                score -= 10
            candidates.append({
                'source': 'fantlab',
                'score': score,
                'title': title,
                'authors': author_names or ['Unknown'],
                'id': item.get('id'),
                'identifier': fantlab_identifier,
                'url': FANTLAB_BASE_URL + '/' + fantlab_identifier if fantlab_identifier else None,
                'comments': item.get('description') or '',
                'rating': (item.get('stat') or {}).get('rating'),
                'cover_url': FANTLAB_API_BASE_URL + item.get('image') if item.get('image') else None,
                'tags': [item.get('name_type')] if item.get('name_type') else [],
            })
        candidates.sort(key=lambda row: row['score'], reverse=True)
        return candidates

    def metadata_from_fantlab_candidate(self, candidate):
        mi = Metadata(candidate.get('title') or '', candidate.get('authors') or ['Unknown'])
        mi.language = 'rus'
        fantlab_id = candidate.get('identifier') or candidate.get('id')
        if fantlab_id:
            fantlab_id = as_unicode(fantlab_id)
            mi.set_identifier(IDENTIFIER_TYPE_FANTLAB, fantlab_id)
        if candidate.get('comments'):
            mi.comments = '<p>%s</p>' % candidate['comments'].replace('\n', '<br/>')
        if candidate.get('tags'):
            mi.tags = candidate['tags']
        try:
            if candidate.get('rating'):
                mi.rating = float(candidate['rating'])
        except Exception:
            pass
        cover_url = candidate.get('cover_url')
        if cover_url and fantlab_id:
            self.cache_cover(fantlab_id, cover_url)
            mi.has_cover = True
        return mi
