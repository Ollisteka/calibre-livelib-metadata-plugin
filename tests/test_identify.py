from plugin_under_test.providers.livelib import provider

from unittest.mock import Mock

import json
import pytest


def candidate(kind, identifier, score=140):
    common = {'source': kind, 'title': 'Книга %s' % identifier,
              'score': score, 'cover_url': 'https://cover/%s' % identifier}
    if kind == 'litres':
        return {**common, 'id': str(identifier), 'authors': ['Автор'],
                'url': 'https://www.litres.ru/book/%s' % identifier}
    if kind == 'livelib':
        return {**common, 'author': 'Автор',
                'url': 'https://www.livelib.ru/book/%s' % identifier}
    if kind == 'fantlab':
        return {**common, 'id': identifier, 'identifier': 'work%s' % identifier,
                'authors': ['Автор'], 'url': 'https://fantlab.ru/work%s' % identifier}
    raise ValueError('Unsupported candidate source: %s' % kind)


def drain(queue):
    return [queue.get_nowait() for _ in range(queue.qsize())]


@pytest.fixture
def searches(source, monkeypatch):
    """Replace both API searches, LiveLib transport and its HTML parser.

    All searches start empty; tests supply candidates or failures explicitly.
    Detail methods are left real unless a scenario replaces them separately.
    """
    doubles = {}
    for name, value in [('search_litres', []), ('search_fantlab', []),
                        ('fetch_livelib_text', 'synthetic html'), ('parse_search_results', [])]:
        doubles[name] = Mock(return_value=value)
        owner = {'search_litres': source.litres, 'search_fantlab': source.fantlab,
                 'fetch_livelib_text': source.transport, 'parse_search_results': provider}[name]
        monkeypatch.setattr(owner, name, doubles[name])
    return doubles


def test_direct_litres_id_also_searches_missing_sources(source, monkeypatch, searches, log, results, abort, clock):
    fetch = Mock(return_value={'payload': {'data': {
        'id': '123', 'title': 'Подробное', 'language_code': 'ru'}}})
    monkeypatch.setattr(source.transport, 'fetch_litres_json', fetch)
    source.identify(log, results, abort, title='Книга', authors=['Автор'], identifiers={'litres': '123'})
    found = drain(results)
    assert len(found) == 1
    assert found[0].identifiers == {'litres': '123'}
    assert (found[0].title, found[0].authors, found[0].language) == ('Подробное', ['Автор'], 'rus')
    assert found[0].source_relevance == -1000
    fetch.assert_called_once_with('https://api.litres.ru/foundation/api/arts/123', 15)
    searches['search_litres'].assert_not_called()
    searches['search_fantlab'].assert_called_once()


def test_direct_livelib_id_detail_error_also_searches_missing_sources(
        source, monkeypatch, searches, log, results, abort, clock):
    fetch = Mock(side_effect=OSError('detail unavailable'))
    monkeypatch.setattr(source.livelib, 'fetch_book', fetch)
    source.identify(log, results, abort, title='Книга', authors=['Автор'], identifiers={'livelib': '123'})
    found = drain(results)
    assert len(found) == 1
    assert found[0].identifiers == {'livelib': '123'}
    assert (found[0].title, found[0].authors, found[0].language) == ('Книга', ['Автор'], 'rus')
    assert found[0].comments is None
    assert found[0].source_relevance == -1000
    fetch.assert_called_once_with(log, 'https://beta.livelib.ru/book/123', 15)
    searches['search_litres'].assert_called_once()
    searches['search_fantlab'].assert_called_once()
    searches['fetch_livelib_text'].assert_not_called()


def test_both_direct_ids_are_fetched(source, monkeypatch, searches, log, results, abort):
    monkeypatch.setattr(source.litres, 'fetch_litres_book', Mock(side_effect=OSError('no details')))
    livelib_details = Mock(side_effect=OSError('no details'))
    monkeypatch.setattr(source.livelib, 'fetch_book', livelib_details)
    source.identify(log, results, abort, title='Книга', identifiers={'litres': '1', 'livelib': '2'})
    assert [mi.identifiers for mi in drain(results)] == [{'litres': '1', 'livelib': '2'}] * 2
    livelib_details.assert_called_once()


def test_direct_livelib_id_with_multiple_page_authors(
        source, monkeypatch, searches, log, results, abort):
    authors = ['Джон Рэйти', 'Эрик Хагерман']
    title = 'Зажги себя! Жизнь — в движении'
    searches['fetch_livelib_text'].return_value = (
        '<script type="application/ld+json">%s</script>' % json.dumps({
            '@type': 'Book', 'name': title, 'author': [{'name': a} for a in authors]}))
    monkeypatch.setattr(provider, 'check_isbn', lambda value: None)
    identifiers = {'isbn': '9785001007616', 'livelib': '1002467643'}
    source.identify(log, results, abort, title=title, authors=authors, identifiers=identifiers)
    found = drain(results)
    assert len(found) == 1
    assert (found[0].title, found[0].authors, found[0].identifiers) == (title, authors, identifiers)
    assert searches['fetch_livelib_text'].call_args.args[0] == 'https://beta.livelib.ru/book/1002467643'


@pytest.mark.parametrize('score, legacy', [
    pytest.param(99, True, id='below-strong-match'),
    pytest.param(100, False, id='at-strong-match'),
    pytest.param(101, False, id='above-strong-match'),
])
@pytest.mark.parametrize('strong_source', ['litres', 'beta'])
def test_legacy_threshold(source, monkeypatch, searches, log, results, abort, score, legacy, strong_source):
    row = candidate('litres' if strong_source == 'litres' else 'livelib', 1, score)
    if strong_source == 'litres':
        searches['search_litres'].return_value = [row]
    else:
        searches['parse_search_results'].side_effect = lambda raw, *args: [row] if raw == 'beta' else []
    searches['fetch_livelib_text'].side_effect = lambda url, timeout: 'beta' if '/search?' in url else 'legacy'
    monkeypatch.setattr(source.litres, 'fetch_litres_book', Mock(side_effect=OSError('no details')))
    monkeypatch.setattr(source.livelib, 'fetch_book', Mock(side_effect=OSError('no details')))
    source.identify(log, results, abort, title='Книга', authors=['Автор'])
    urls = [call.args[0] for call in searches['fetch_livelib_text'].call_args_list]
    assert len(urls) == (2 if legacy else 1)
    assert any('/find/' in url for url in urls) is legacy
    found = drain(results)
    assert len(found) == 1
    assert found[0].source_relevance == -score
    searches['search_fantlab'].assert_called_once()


def test_merge_sources_orders_by_score_and_limits_to_six(source, monkeypatch, searches, log, results, abort):
    searches['search_litres'].return_value = [candidate('litres', 1, 145), candidate('litres', 2, 80)]
    livelib_candidates = [candidate('livelib', 3, 148), candidate('livelib', 4, 90)]
    searches['parse_search_results'].return_value = livelib_candidates
    searches['search_fantlab'].return_value = [candidate('fantlab', i, score) for i, score in [(5, 140), (6, 130), (7, 70)]]
    # Supply successful detail results; error fallback is covered separately below.
    monkeypatch.setattr(source.litres, 'fetch_litres_book',
                        lambda log, row, timeout: source.litres.metadata_from_litres_candidate(row))
    livelib_by_url = {row['url']: row for row in livelib_candidates}
    monkeypatch.setattr(source.livelib, 'fetch_book', lambda log, url, timeout:
                        source.livelib.metadata_from_search_candidate(livelib_by_url[url]))
    source.identify(log, results, abort, title='Книга', authors=['Автор'])
    found = drain(results)
    assert [mi.title for mi in found] == ['Книга 3', 'Книга 1', 'Книга 5', 'Книга 6', 'Книга 4', 'Книга 2']
    assert [mi.source_relevance for mi in found] == [-148, -145, -140, -130, -90, -80]


@pytest.mark.parametrize('kind, expected_language, expected_cover', [
    pytest.param('litres', None, 'https://cdn.litres.ru/pub/c/cover_415/1', id='litres-detail-error'),
    pytest.param('livelib', 'rus', 'https://cover/1', id='livelib-detail-error'),
])
def test_detail_error_preserves_candidate_metadata_and_caches_cover(
        source, monkeypatch, searches, log, results, abort, kind, expected_language, expected_cover, clock):
    row = candidate(kind, 1)
    search = 'search_litres' if kind == 'litres' else 'parse_search_results'
    searches[search].return_value = [row]
    detail_method = 'fetch_litres_book' if kind == 'litres' else 'fetch_book'
    details = Mock(side_effect=OSError('no details'))
    monkeypatch.setattr(source.litres if kind == 'litres' else source.livelib, detail_method, details)
    source.identify(log, results, abort, title='Книга', authors=['Автор'], timeout=7)
    found = drain(results)
    assert len(found) == 1
    mi = found[0]
    assert (mi.title, mi.authors, mi.language) == ('Книга 1', ['Автор'], expected_language)
    assert mi.identifiers == {kind: '1'}
    assert mi.has_cover
    assert source.get_cached_cover_url(mi.identifiers) == expected_cover
    details.assert_called_once_with(log, row if kind == 'litres' else row['url'], 7)


@pytest.mark.parametrize('title', ['Book', ''])
def test_missing_detail_uses_search_candidate(source, monkeypatch, searches, log, results, abort, title):
    row = candidate('livelib', 1)
    row['title'] = title
    searches['parse_search_results'].return_value = [row]
    # A real page without Book JSON-LD yields None from fetch_book.
    source.identify(log, results, abort, title='Book')
    if not title:
        assert results.empty()
    else:
        mi = results.get_nowait()
        assert mi.title == title
        assert mi.has_cover
        assert source.get_cached_cover_url(mi.identifiers) == 'https://cover/1'


def test_search_failures_allow_other_sources(source, searches, log, results, abort):
    searches['fetch_livelib_text'].side_effect = OSError('unavailable')
    searches['search_fantlab'].return_value = [candidate('fantlab', 1)]
    source.identify(log, results, abort, title='Книга')
    assert [mi.identifiers for mi in drain(results)] == [{'fantlab': 'work1'}]


def test_empty_identify(source, searches, log, results, abort):
    source.identify(log, results, abort)
    assert results.empty()
    for search in searches.values():
        search.assert_not_called()


def test_cancelled_direct_lookup(source, monkeypatch, searches, log, results, abort):
    abort.set()
    fetch = Mock()
    monkeypatch.setattr(source.litres, 'fetch_litres_book', fetch)
    source.identify(log, results, abort, identifiers={'litres': '1'})
    fetch.assert_not_called()
    assert results.empty()


def test_cancellation_after_search_before_details(source, monkeypatch, searches, log, results, abort):
    def search(*args, **kwargs):
        abort.set()
        return [candidate('litres', 1)]
    searches['search_litres'].side_effect = search
    fetch = Mock()
    monkeypatch.setattr(source.litres, 'fetch_litres_book', fetch)
    source.identify(log, results, abort, title='Книга')
    fetch.assert_not_called()
    assert results.empty()


def test_cancelled_search_never_calls_providers(source, searches, log, results, abort):
    abort.set()
    source.identify(log, results, abort, title='Book')
    for search in searches.values():
        search.assert_not_called()


def test_cancel_during_litres_stops_following_requests(source, monkeypatch, searches, log, results, abort):
    def search(*args, **kwargs):
        abort.set()
        return []
    searches['search_litres'].side_effect = search
    source.identify(log, results, abort, title='Book')
    searches['fetch_livelib_text'].assert_not_called()
    searches['search_fantlab'].assert_not_called()


def test_cancel_between_litres_queries(source, monkeypatch, log, abort):
    def fetch(*args):
        abort.set()
        return {}
    fetch = Mock(side_effect=fetch)
    monkeypatch.setattr(source.transport, 'fetch_litres_json', fetch)
    source.litres.search_litres(log, 'Book', ['Author'], 7, abort=abort)
    fetch.assert_called_once()
