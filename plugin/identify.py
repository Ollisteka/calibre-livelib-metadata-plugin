from .config import SOURCE_NAMES
from .constants import BASE_URL, BETA_BASE_URL
from .merging import enrich_results, missing
from calibre import as_unicode
from time import monotonic
from urllib.parse import quote


STRONG_MATCH_SCORE = 100


def identify(litres, livelib, fantlab, log, result_queue, abort, title=None, authors=None,
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

    def search(call, *args, budget=None, **kwargs):
        limit = remaining() if budget is None else min(remaining(), budget)
        if stopped() or limit <= 0:
            return []
        try:
            return call(*args, timeout=limit, **kwargs) or []
        except Exception as err:
            log.exception('Source search failed: %s' % as_unicode(err))
            return []

    def fetch(candidate, budget=None):
        if stopped():
            return None
        limit = remaining() if budget is None else min(remaining(), budget)
        kind = candidate.get('source', 'livelib')
        if kind == 'litres':
            try:
                mi = litres.fetch_litres_book(log, candidate, limit)
            except Exception as err:
                log.exception('LitRes detail failed for %s: %s' % (candidate.get('id'), as_unicode(err)))
                mi = litres.metadata_from_litres_candidate(candidate)
        elif kind == 'fantlab':
            if candidate.get('direct'):
                try:
                    mi = fantlab.fetch_book(log, candidate['identifier'], limit)
                except Exception as err:
                    log.exception('FantLab detail failed: %s' % as_unicode(err))
                    mi = fantlab.metadata_from_fantlab_candidate(candidate)
            else:
                mi = fantlab.metadata_from_fantlab_candidate(candidate)
        else:
            mi = livelib.complete_candidate(log, candidate, limit)
        if mi is not None:
            mi.source_relevance = -candidate['score']
            rows.append((kind, mi))
        return mi

    direct_pending = [kind for kind in SOURCE_NAMES if kind in enabled and identifiers.get(kind)]
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
        # Reserve a share for missing-source searches and details.
        reserve = int(any(k in enabled and not identifiers.get(k) for k in SOURCE_NAMES))
        mi = fetch(candidate, budget=remaining() / (len(direct_pending) + reserve))
        direct_pending.remove(kind)
        if mi is not None:
            direct_results.append(mi)
            if len(direct_results) == 1:
                title = mi.title if not missing(mi, 'title') else title
                authors = mi.authors if not missing(mi, 'authors') else authors

    query = ' '.join([title or ''] + list(authors or [])).strip()
    candidates = []
    if query and not stopped():
        pending = [kind for kind in SOURCE_NAMES if kind in enabled and not identifiers.get(kind)]
        for index, kind in enumerate(pending):
            if stopped():
                break
            # One share per remaining source, plus a share for book details.
            # Fast searches leave their unused time available to later work.
            budget = remaining() / (len(pending) - index + 1)
            if kind == 'litres':
                candidates.extend(search(litres.search_litres, log, title, authors, budget=budget, abort=abort))
            elif kind == 'livelib':
                source_deadline = monotonic() + budget
                url = BETA_BASE_URL + '/search?q=' + quote(query)
                candidates.extend(search(livelib.search_page, url, title, authors,
                                         budget=budget / 2, log=log))
                # Preserve the strong-match threshold for legacy escalation.
                if not any(c['score'] >= STRONG_MATCH_SCORE for c in candidates):
                    url = BASE_URL + '/find/' + quote(query)
                    candidates.extend(search(livelib.search_page, url, title, authors,
                                             budget=source_deadline - monotonic(), log=log))
            else:
                candidates.extend(search(fantlab.search_fantlab, log, title, authors, budget=budget))
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
    for index, candidate in enumerate(selected):
        fetch(candidate, budget=remaining() / (len(selected) - index))
        if abort.is_set():
            return
    rows.sort(key=lambda row: row[1].source_relevance)
    # A known ID anchors the lookup. Other hits are donors, not alternative
    # books to which the user's existing IDs should be attached.
    results = [mi for mi in enrich_results(rows, identifiers, log,
                                      blocked_sources={c.get('source', 'livelib') for c in candidates
                                                       if c not in selected})
               if not direct_results or any(mi is direct for direct in direct_results)]
    if enrich_personal is not None:
        # In personal mode, aggregate ratings must never stand in for the
        # reader's own rating, even if the shelf lookup fails or times out.
        for mi in results:
            mi.rating = None
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
