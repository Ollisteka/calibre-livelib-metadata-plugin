from .constants import BASE_URL
from .constants import BETA_BASE_URL
from .constants import IDENTIFIER_TYPE_LITRES
from .constants import IDENTIFIER_TYPE_LIVELIB
from .identifiers import livelib_id_from_url
from calibre import as_unicode
from urllib.parse import quote


STRONG_MATCH_SCORE = 100


def identify(litres, livelib, fantlab, cache_cover, log, result_queue, abort, title=None, authors=None,
             identifiers=None, timeout=30):
    """Search concrete providers and emit at most six results, caching URLs only."""
    identifiers = identifiers or {}
    direct_id = identifiers.get(IDENTIFIER_TYPE_LIVELIB)
    candidates = []

    litres_id = identifiers.get(IDENTIFIER_TYPE_LITRES)
    if litres_id:
        candidates.append({
            'source': 'litres',
            'score': 1000,
            'id': litres_id,
            'title': title or '',
            'authors': authors or [],
        })
    elif direct_id:
        candidates.append({
            'source': 'livelib',
            'score': 1000,
            'url': BETA_BASE_URL + '/book/' + direct_id,
            'title': title or '',
            'author': (authors or [''])[0],
        })
    else:
        query = ' '.join([title or ''] + list(authors or [])).strip()
        if not query:
            return
        candidates = litres.search_litres(log, title, authors, timeout)
        # Always run the fast beta search; only fall back to the slow legacy
        # livelib.ru/find search when nothing strong has been found yet.
        search_urls = [BETA_BASE_URL + '/search?q=' + quote(query)]
        for url in search_urls:
            log.info('LiveLib search: ' + url)
            found = livelib.search_page(url, title, authors, timeout, log=log)
            if found:
                candidates.extend(found)
        if not any(c['score'] >= STRONG_MATCH_SCORE for c in candidates):
            legacy_url = BASE_URL + '/find/' + quote(query)
            log.info('LiveLib search: ' + legacy_url)
            found = livelib.search_page(legacy_url, title, authors, timeout, log=log)
            if found:
                candidates.extend(found)
        candidates.extend(fantlab.search_fantlab(log, title, authors, timeout))
        candidates.sort(key=lambda row: row['score'], reverse=True)

    for candidate in candidates[:6]:
        if abort.is_set():
            return
        if candidate.get('source') == 'litres':
            try:
                mi = litres.fetch_litres_book(log, candidate, timeout)
            except Exception as err:
                log.exception('LitRes detail failed for %s: %s' % (candidate.get('id'), as_unicode(err)))
                mi = litres.metadata_from_litres_candidate(candidate)
        elif candidate.get('source') == 'fantlab':
            mi = fantlab.metadata_from_fantlab_candidate(candidate)
        else:
            try:
                mi = livelib.fetch_book(log, candidate['url'], timeout)
            except Exception as err:
                log.exception('LiveLib detail failed for %s: %s' % (candidate['url'], as_unicode(err)))
                mi = livelib.metadata_from_search_candidate(candidate)
            if mi is not None and candidate.get('cover_url'):
                livelib_id = (mi.identifiers or {}).get(IDENTIFIER_TYPE_LIVELIB) or livelib_id_from_url(candidate.get('url'))
                if livelib_id:
                    cache_cover(livelib_id, candidate['cover_url'])
                    mi.has_cover = True
        if mi is None:
            continue
        # Cover bytes are intentionally NOT downloaded here. Calibre fetches
        # covers separately via download_cover() using the URLs cached above,
        # so downloading them during identify would only duplicate the work.
        mi.source_relevance = -candidate['score']
        result_queue.put(mi)
