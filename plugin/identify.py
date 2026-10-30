from .config import SOURCE_NAMES
from .constants import BASE_URL, BETA_BASE_URL
from .identifiers import livelib_id_from_url
from .merging import enrich_results, missing
from calibre import as_unicode
from time import monotonic
from urllib.parse import quote


STRONG_MATCH_SCORE = 100


def identify(litres, livelib, fantlab, cache_cover, log, result_queue, abort, title=None, authors=None,
             identifiers=None, timeout=30, enabled=None, enrich_personal=None):
    """Search enabled providers, enrich results, and emit at most six candidates."""
    identifiers = identifiers or {}
    enabled = frozenset(SOURCE_NAMES if enabled is None else enabled)
    deadline = monotonic() + timeout
    rows = []
    direct_results = []

    def remaining():
        return max(0.0, deadline - monotonic())

    def stopped():
        return abort.is_set() or remaining() <= 0

    def search(call, *args, **kwargs):
        if stopped():
            return []
        try:
            return call(*args, timeout=remaining(), **kwargs) or []
        except Exception as err:
            log.exception('Source search failed: %s' % as_unicode(err))
            return []

    def fetch(candidate):
        if stopped():
            return None
        kind = candidate.get('source', 'livelib')
        if kind == 'litres':
            try:
                mi = litres.fetch_litres_book(log, candidate, remaining())
            except Exception as err:
                log.exception('LitRes detail failed for %s: %s' % (candidate.get('id'), as_unicode(err)))
                mi = litres.metadata_from_litres_candidate(candidate)
        elif kind == 'fantlab':
            if candidate.get('direct'):
                try:
                    mi = fantlab.fetch_book(log, candidate['identifier'], remaining())
                except Exception as err:
                    log.exception('FantLab detail failed: %s' % as_unicode(err))
                    mi = fantlab.metadata_from_fantlab_candidate(candidate)
            else:
                mi = fantlab.metadata_from_fantlab_candidate(candidate)
        else:
            mi = livelib.complete_candidate(log, candidate, remaining())
        if mi is not None:
            mi.source_relevance = -candidate['score']
            rows.append((kind, mi))
        return mi

    for kind in SOURCE_NAMES:
        if kind not in enabled:
            log.info('Source disabled: %s' % kind)
            continue
        identifier = identifiers.get(kind)
        if not identifier:
            continue
        candidate = dict(source=kind, score=1000, title=title or '', authors=authors or [],
                         author=(authors or [''])[0], id=identifier, identifier=identifier,
                         direct=True)
        if kind == 'livelib':
            candidate['url'] = BETA_BASE_URL + '/book/' + identifier
        mi = fetch(candidate)
        if mi is not None:
            direct_results.append(mi)
            if len(direct_results) == 1:
                title = mi.title if not missing(mi, 'title') else title
                authors = mi.authors if not missing(mi, 'authors') else authors

    query = ' '.join([title or ''] + list(authors or [])).strip()
    candidates = []
    if query and not stopped():
        if 'litres' in enabled and not identifiers.get('litres'):
            candidates.extend(search(litres.search_litres, log, title, authors, abort=abort))
        if 'livelib' in enabled and not identifiers.get('livelib'):
            url = BETA_BASE_URL + '/search?q=' + quote(query)
            log.info('LiveLib search: ' + url)
            candidates.extend(search(livelib.search_page, url, title, authors, log=log))
            # Preserve the author's strong-match threshold for legacy escalation.
            if not any(c['score'] >= STRONG_MATCH_SCORE for c in candidates):
                url = BASE_URL + '/find/' + quote(query)
                log.info('LiveLib search: ' + url)
                candidates.extend(search(livelib.search_page, url, title, authors, log=log))
        if 'fantlab' in enabled and not identifiers.get('fantlab'):
            candidates.extend(search(fantlab.search_fantlab, log, title, authors))
        candidates.sort(key=lambda row: row['score'], reverse=True)

    # Reserve a slot for each source before filling the six-result budget, so a
    # long list from one provider cannot crowd out another provider's identifier.
    selected = []
    for kind in SOURCE_NAMES:
        first = next((c for c in candidates if c.get('source', 'livelib') == kind), None)
        if first is not None:
            selected.append(first)
    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
    selected = selected[:max(0, 6 - len(rows))]
    selected.sort(key=lambda row: row['score'], reverse=True)
    for candidate in selected:
        fetch(candidate)
        if abort.is_set():
            return
    rows.sort(key=lambda row: row[1].source_relevance)
    # A known ID anchors the lookup. Other hits are donors, not alternative
    # books to which the user's existing IDs should be attached.
    results = [mi for mi in enrich_results(rows, identifiers, log,
                                      blocked_sources={c.get('source', 'livelib') for c in candidates
                                                       if c not in selected})
               if not direct_results or any(mi is direct for direct in direct_results)]
    if enrich_personal is not None and results and not stopped():
        try:
            enrich_personal(results, remaining())
        except Exception as err:
            log.exception('LiveLib reading history unavailable: %s' % as_unicode(err))
    for mi in results:
        if abort.is_set():
            return
        # Providers use the library's 0..10 scale internally. The metadata
        # download API expects 0..5; Calibre doubles it when applying a result.
        if mi.rating is not None:
            mi.rating /= 2
        result_queue.put(mi)
