from ..constants import IDENTIFIER_TYPE_LITRES
from ..constants import LITRES_API_BASE
from ..constants import LITRES_WEB_BASE
from ..matching import norm
from ..matching import score_match
from ..matching import title_match_enough
from calibre import as_unicode
from calibre.ebooks.metadata.book.base import Metadata
from urllib.parse import quote
from urllib.parse import urlencode


class LitresProvider:
    """LitRes candidates carry source, score, string id and authors (a list)."""

    def __init__(self, transport, cache_cover):
        self.transport = transport
        self.cache_cover = cache_cover

    def absolutize_litres_cover(self, cover_url, art_id=None):
        if art_id:
            return 'https://cdn.litres.ru/pub/c/cover_415/%s' % art_id
        if not cover_url:
            return None
        if cover_url.startswith('//'):
            return 'https:' + cover_url
        if cover_url.startswith('/pub/'):
            return 'https://cdn.litres.ru' + cover_url
        if cover_url.startswith('/'):
            return LITRES_WEB_BASE + cover_url
        return cover_url

    def search_litres(self, log, query_title, query_authors, timeout):
        queries = []
        if query_title:
            queries.append(' '.join([query_title] + list(query_authors or [])).strip())
            queries.append(query_title)
        candidates = []
        seen = set()
        for query in [q for q in queries if q]:
            params = [
                ('q', query), ('limit', '10'), ('offset', '0'),
                ('is_for_pda', 'false'), ('o', 'popular'),
                ('show_unavailable', 'false'),
            ]
            for type_name in ('text_book', 'audiobook', 'paper_book', 'podcast', 'podcast_episode', 'webtoon'):
                params.append(('types', type_name))
            url = LITRES_API_BASE + '/search?' + urlencode(params)
            log.info('LitRes search: ' + url)
            try:
                payload = self.transport.fetch_json(url, timeout).get('payload') or {}
            except Exception as err:
                log.exception('LitRes search failed: %s' % as_unicode(err))
                continue
            for row in payload.get('data') or []:
                item = row.get('instance') or row
                art_id = item.get('id')
                if not art_id or art_id in seen:
                    continue
                persons = item.get('persons') or []
                authors = [p.get('full_name') for p in persons if p.get('role') == 'author' and p.get('full_name')]
                author_text = ', '.join(authors or [p.get('full_name') for p in persons if p.get('full_name')][:2])
                if query_authors and authors:
                    query_author_tokens = set(norm(' '.join(query_authors)).split())
                    result_author_tokens = set(norm(' '.join(authors)).split())
                    if not (query_author_tokens & result_author_tokens):
                        continue
                if not title_match_enough(query_title, item.get('title') or ''):
                    continue
                score = score_match(query_title, query_authors, item.get('title') or '', author_text)
                item_url = item.get('url') or ''
                if item.get('art_type') in (4, 10) or '/audiobook/' in item_url or '/podcast/' in item_url:
                    score -= 20
                if score < 55:
                    continue
                seen.add(art_id)
                cover_url = self.absolutize_litres_cover(item.get('cover_url'), art_id)
                candidates.append({
                    'source': 'litres',
                    'score': score + 5,
                    'id': str(art_id),
                    'title': item.get('title') or '',
                    'authors': authors or (author_text.split(', ') if author_text else ['Unknown']),
                    'url': item.get('url'),
                    'cover_url': cover_url,
                    'raw': item,
                })
        candidates.sort(key=lambda row: row['score'], reverse=True)
        return candidates

    def metadata_from_litres_candidate(self, candidate, item=None):
        item = item or candidate.get('raw') or {}
        title = item.get('title') or candidate.get('title') or ''
        persons = item.get('persons') or []
        authors = [p.get('full_name') for p in persons if p.get('role') == 'author' and p.get('full_name')]
        if not authors:
            authors = candidate.get('authors') or ['Unknown']
        mi = Metadata(title, authors)
        if (item.get('language_code') or '').lower() == 'ru':
            mi.language = 'rus'
        litres_id = str(item.get('id') or candidate.get('id') or '')
        if litres_id:
            mi.set_identifier(IDENTIFIER_TYPE_LITRES, litres_id)
        publishers = [p.get('full_name') for p in persons if p.get('role') == 'publisher' and p.get('full_name')]
        if publishers:
            mi.publisher = publishers[0]
        description = item.get('annotation') or item.get('description')
        if not description:
            meta = item.get('meta_tags') or {}
            root_meta = meta.get('root') if isinstance(meta, dict) else None
            if isinstance(root_meta, dict):
                description = root_meta.get('open_graph_description') or root_meta.get('description')
        if description:
            mi.comments = '<p>%s</p>' % as_unicode(description).strip()
        genres = item.get('genres') or item.get('genres_hierarchy') or []
        tags = []
        for genre in genres:
            if isinstance(genre, dict):
                name = genre.get('title') or genre.get('name')
                if name:
                    tags.append(name)
            elif genre:
                tags.append(as_unicode(genre))
        if tags:
            mi.tags = tags[:8]
        rating = item.get('rating') or {}
        try:
            value = rating.get('rated_avg') if isinstance(rating, dict) else rating
            if value:
                mi.rating = float(value) * 2 if float(value) <= 5 else float(value)
        except Exception:
            pass
        cover_url = self.absolutize_litres_cover(item.get('cover_url') or candidate.get('cover_url'), litres_id)
        if cover_url and litres_id:
            self.cache_cover(litres_id, cover_url)
            mi.has_cover = True
        return mi

    def fetch_litres_book(self, log, candidate, timeout):
        art_id = candidate.get('id')
        if not art_id:
            return self.metadata_from_litres_candidate(candidate)
        url = LITRES_API_BASE + '/arts/' + quote(str(art_id))
        log.info('LitRes detail: ' + url)
        payload = self.transport.fetch_json(url, timeout).get('payload') or {}
        item = payload.get('data') or payload
        return self.metadata_from_litres_candidate(candidate, item=item)
