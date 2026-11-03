from itertools import product
from unittest.mock import Mock

import pytest

from calibre.ebooks.metadata.book.base import Metadata
from plugin_under_test.config import SOURCE_NAMES
from plugin_under_test.merging import enrich_results


def metadata(kind, identifier, title='Книга', authors=None, **fields):
    mi = Metadata(title, authors or ['Автор'])
    mi.set_identifier(kind, identifier)
    for key, value in fields.items():
        setattr(mi, key, value)
    return mi


def setup_sources(source, monkeypatch):
    rows = {
        'litres': {'source': 'litres', 'score': 145, 'id': '1', 'title': 'Книга', 'authors': ['Автор']},
        'livelib': {'source': 'livelib', 'score': 148, 'url': 'https://beta.livelib.ru/book/2', 'title': 'Книга', 'author': 'Автор'},
        'fantlab': {'source': 'fantlab', 'score': 140, 'identifier': 'work3', 'title': 'Книга', 'authors': ['Автор']},
    }
    searches = []
    for owner, method, kind in [(source.litres, 'search_litres', 'litres'),
                                (source.livelib, 'search_page', 'livelib'),
                                (source.fantlab, 'search_fantlab', 'fantlab')]:
        search = Mock(return_value=[rows[kind]])
        monkeypatch.setattr(owner, method, search)
        searches.append(search)
    monkeypatch.setattr(source.litres, 'fetch_litres_book',
                        lambda *args: metadata('litres', '1', publisher='Издатель'))
    monkeypatch.setattr(source.livelib, 'fetch_book',
                        lambda *args: metadata('livelib', '2', comments='Аннотация'))
    monkeypatch.setattr(source.fantlab, 'metadata_from_fantlab_candidate',
                        lambda *args: metadata('fantlab', 'work3', tags=['Фантастика']))
    return searches


def test_collects_three_ids_and_complements_fields(source, monkeypatch, log, results, abort):
    setup_sources(source, monkeypatch)
    source.identify(log, results, abort, title='Книга', authors=['Автор'])
    found = [results.get_nowait() for _ in range(results.qsize())]
    assert len(found) == 3
    for mi in found:
        assert mi.identifiers == {'litres': '1', 'livelib': '2', 'fantlab': 'work3'}
        assert (mi.publisher, mi.comments, mi.tags) == ('Издатель', 'Аннотация', ['Фантастика'])


@pytest.mark.parametrize('switches', list(product((False, True), repeat=3)))
def test_enabled_source_combinations(source, monkeypatch, log, results, abort, switches):
    searches = setup_sources(source, monkeypatch)
    for kind, enabled in zip(SOURCE_NAMES, switches):
        source.prefs['use_' + kind] = enabled
    source.identify(log, results, abort, title='Книга', authors=['Автор'])
    assert results.qsize() == sum(switches)
    for search, enabled in zip(searches, switches):
        assert bool(search.call_count) == enabled
    while not results.empty():
        assert set(results.get_nowait().identifiers) == {kind for kind, on in zip(SOURCE_NAMES, switches) if on}


def test_existing_id_is_enriched_without_searching_that_source(source, monkeypatch, log, results, abort):
    searches = setup_sources(source, monkeypatch)
    source.identify(log, results, abort, identifiers={'litres': '1'})
    assert results.qsize() == 1
    assert results.get_nowait().identifiers == {'litres': '1', 'livelib': '2', 'fantlab': 'work3'}
    searches[0].assert_not_called()
    searches[1].assert_called_once()
    searches[2].assert_called_once()


def test_populated_fields_are_preserved_and_lists_are_not_aliased(log):
    primary = metadata('litres', '1', comments='Основное', tags=['Роман'], rating=8,
                       publisher='Исходное')
    donor = metadata('livelib', '2', comments='Другая аннотация', tags=['Фантастика'],
                     rating=10, publisher='Другое', isbn='isbn')
    found = enrich_results([('litres', primary), ('livelib', donor)], {}, log)
    assert (primary.comments, primary.tags, primary.rating, primary.publisher) == ('Основное', ['Роман'], 8, 'Исходное')
    assert primary.isbn == 'isbn'
    assert found[1].comments == 'Другая аннотация'
    empty = metadata('fantlab', 'work3')
    enrich_results([('fantlab', empty), ('litres', primary)], {}, log)
    empty.tags.append('Новое')
    assert primary.tags == ['Роман']


def test_different_books_and_ambiguous_ids_do_not_enrich(log):
    primary = metadata('litres', '1')
    rows = [('litres', primary), ('livelib', metadata('livelib', '2', title='Другая книга', publisher='Чужое')),
            ('fantlab', metadata('fantlab', 'work3', tags=['Первое'])),
            ('fantlab', metadata('fantlab', 'work4', tags=['Второе']))]
    enrich_results(rows, {}, log)
    assert primary.identifiers == {'litres': '1'}
    assert primary.publisher is None
    assert primary.tags == []


def test_existing_conflicting_and_disabled_ids_are_preserved(log):
    primary = metadata('litres', '1')
    donor = metadata('livelib', '2', publisher='Не переносить')
    enrich_results([('litres', primary), ('livelib', donor)], {'livelib': 'original', 'other': 'x'}, log)
    assert primary.identifiers == {'litres': '1', 'livelib': 'original', 'other': 'x'}
    assert primary.publisher is None


def test_direct_id_does_not_attach_to_unrelated_search_hits(source, monkeypatch, log, results, abort):
    setup_sources(source, monkeypatch)
    monkeypatch.setattr(source.livelib, 'fetch_book', lambda *args: metadata('livelib', '2', title='Другое'))
    monkeypatch.setattr(source.fantlab, 'metadata_from_fantlab_candidate', lambda *args: metadata('fantlab', 'work3', authors=['Другой']))
    source.identify(log, results, abort, identifiers={'litres': '1'})
    assert results.qsize() == 1
    assert results.get_nowait().identifiers == {'litres': '1'}


def test_all_sources_disabled_blocks_direct_ids_cached_covers_and_fallback(source, monkeypatch, log, results, abort):
    for kind in SOURCE_NAMES:
        source.prefs['use_' + kind] = False
        source._cover_cache_writer(kind)('1', 'https://cover/' + kind)
    # The suite's network guard catches any unexpected request.
    ids = {'litres': '1', 'livelib': '1', 'fantlab': 'work1'}
    source.identify(log, results, abort, title='Книга', authors=['Автор'], identifiers=ids)
    assert results.empty()
    assert source.get_cached_cover_url(ids) is None
    downloader = Mock()
    monkeypatch.setattr(source, 'download_multiple_covers', downloader)
    source.download_cover(log, results, abort, title='Книга', authors=['Автор'], identifiers=ids)
    downloader.assert_not_called()


def test_cover_cache_is_separated_by_source_and_filters_disabled_sources(source):
    for kind in SOURCE_NAMES:
        source._cover_cache_writer(kind)('1', 'https://cover/' + kind)
    ids = dict.fromkeys(SOURCE_NAMES, '1')
    assert source.covers.get_cached_cover_urls(ids) == ['https://cover/' + kind for kind in SOURCE_NAMES]
    source.prefs['use_litres'] = False
    assert source.covers.get_cached_cover_urls(ids) == ['https://cover/livelib', 'https://cover/fantlab']


def test_cover_fallback_respects_enabled_sources(source, monkeypatch, log, abort):
    source.prefs.update(use_litres=False, use_livelib=False)
    monkeypatch.setattr(source, 'identify', Mock())
    fantlab = Mock(return_value=[{'cover_url': 'https://cover/fantlab'}])
    monkeypatch.setattr(source.fantlab, 'search_fantlab', fantlab)
    assert source.covers.find_all_cover_urls(log, abort, 'Книга', ['Автор'], {}, 7) == ['https://cover/fantlab']
    fantlab.assert_called_once()


@pytest.mark.parametrize('identifier, parameter, block', [('work33', 'w=33', 'works'), ('edition42', 'e=42', 'editions')])
def test_fantlab_direct_lookup(source, monkeypatch, log, results, abort, identifier, parameter, block):
    import json
    number = ''.join(c for c in identifier if c.isdigit())
    payload = {block: [{'id': int(number), 'name': 'Книга', 'creators': {'authors': [{'name': 'Автор'}]}, 'image': '/image.jpg'}]}
    fetch = Mock(return_value=json.dumps(payload))
    monkeypatch.setattr(source.transport, 'fetch_fantlab_json', lambda url, timeout: json.loads(fetch(url, timeout)))
    source.prefs.update(use_litres=False, use_livelib=False)
    source.identify(log, results, abort, identifiers={'fantlab': identifier})
    mi = results.get_nowait()
    assert mi.identifiers == {'fantlab': identifier}
    assert mi.title == 'Книга'
    assert source.get_cached_cover_url(mi.identifiers) == 'https://api.fantlab.ru/image.jpg'
    assert fetch.call_args.args[0] == 'https://api.fantlab.ru/search-ids?' + parameter


def test_timeout_stops_later_sources_but_returns_partial_result(source, monkeypatch, log, results, abort):
    import importlib
    identify_module = importlib.import_module('plugin_under_test.identify')
    now = [0]
    monkeypatch.setattr(identify_module, 'monotonic', lambda: now[0])
    def direct(*args):
        now[0] = 10
        return metadata('litres', '1')
    monkeypatch.setattr(source.litres, 'fetch_litres_book', direct)
    source.identify(log, results, abort, identifiers={'litres': '1'}, timeout=5)
    assert results.get_nowait().identifiers == {'litres': '1'}

@pytest.mark.parametrize('disabled', SOURCE_NAMES)
def test_disabled_source_with_existing_id_is_never_fetched(source, monkeypatch, log, results, abort, disabled):
    from offline_support import UnexpectedNetwork
    setup_sources(source, monkeypatch)
    monkeypatch.setattr(source.fantlab, 'fetch_book', lambda *args: metadata('fantlab', 'work3'))
    source.prefs['use_' + disabled] = False
    provider = getattr(source, disabled)
    method = 'fetch_litres_book' if disabled == 'litres' else 'fetch_book'
    forbidden = Mock(side_effect=UnexpectedNetwork('Disabled source was accessed'))
    monkeypatch.setattr(provider, method, forbidden)
    ids = {'litres': '1', 'livelib': '2', 'fantlab': 'work3'}
    source.identify(log, results, abort, title='Книга', authors=['Автор'], identifiers=ids)
    forbidden.assert_not_called()
    assert results.qsize() == 2
    while not results.empty():
        assert results.get_nowait().identifiers == ids


def test_unknown_authors_do_not_create_false_correspondence(log):
    first = metadata('litres', '1', authors=['Unknown'], publisher='Одно')
    second = metadata('livelib', '2', authors=['Unknown'], comments='Другое')
    enrich_results([('litres', first), ('livelib', second)], {}, log)
    assert first.identifiers == {'litres': '1'}
    assert first.comments is None


def test_ambiguous_primary_source_does_not_borrow_another_id(log):
    first = metadata('litres', '1')
    second = metadata('litres', '2')
    third = metadata('livelib', '3')
    enrich_results([('litres', first), ('litres', second), ('livelib', third)], {}, log)
    assert first.identifiers == {'litres': '1'}
    assert second.identifiers == {'litres': '2'}
    assert third.identifiers == {'livelib': '3'}


@pytest.mark.parametrize('crowded', ['litres', 'livelib'])
def test_unchecked_candidates_block_id_borrowing(source, monkeypatch, log, results, abort, crowded):
    setup_sources(source, monkeypatch)
    rows = [{'source': crowded, 'score': 160 - i, 'id': str(i),
             'url': 'https://beta.livelib.ru/book/' + str(i),
             'title': 'Book', 'authors': ['Author'], 'author': 'Author'} for i in range(7)]
    method = 'search_litres' if crowded == 'litres' else 'search_page'
    monkeypatch.setattr(getattr(source, crowded), method, lambda *a, **kw: rows)
    source.identify(log, results, abort, title='Book', authors=['Author'])
    found = [results.get_nowait() for _ in range(results.qsize())]
    assert len(found) == 6
    for mi in found:
        if crowded in mi.identifiers:
            assert len(mi.identifiers) == 1
        else:
            assert crowded not in mi.identifiers
