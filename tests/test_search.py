from plugin_under_test.providers import litres

import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest


def litres_item(identifier, title='Книга', author='Автор', **extra):
    return {'id': identifier, 'title': title,
            'persons': [{'role': 'author', 'full_name': author}], **extra}


def test_litres_combines_queries_sorts_and_deduplicates(source, monkeypatch, log):
    audiobook = litres_item(1, art_type=4)
    text_book = litres_item(2)
    duplicate_book = dict(text_book)
    rows = [audiobook, text_book, duplicate_book]
    fetch = Mock(return_value={'payload': {'data': rows}})
    monkeypatch.setattr(source.transport, 'fetch_json', fetch)
    found = source.litres.search_litres(log, 'Книга', ['Автор'], 7)
    # Exact title + author = 140; audio loses 20; accepted results get +5.
    assert [(c['id'], c['score']) for c in found] == [('2', 145), ('1', 125)]
    queries = [parse_qs(urlsplit(call.args[0]).query)['q'] for call in fetch.call_args_list]
    assert queries == [['Книга Автор'], ['Книга']]


@pytest.mark.parametrize('item', [
    pytest.param(litres_item(1, title='Иное'), id='wrong-title'),
    pytest.param(litres_item(1, author='Другой'), id='wrong-author'),
    pytest.param({'title': 'Книга'}, id='missing-id'),
])
def test_litres_rejects_irrelevant_or_unidentifiable_items(source, monkeypatch, log, item):
    monkeypatch.setattr(source.transport, 'fetch_json', Mock(return_value={'payload': {'data': [item]}}))
    assert source.litres.search_litres(log, 'Книга', ['Автор'], 7) == []


def test_litres_unwraps_instance_and_prepares_author_and_cover(source, monkeypatch, log):
    monkeypatch.setattr(source.transport, 'fetch_json', Mock(return_value={
        'payload': {'data': [{'instance': litres_item(5)}]}}))
    found = source.litres.search_litres(log, 'Книга', ['Автор'], 7)
    assert len(found) == 1
    assert found[0]['id'] == '5'
    assert found[0]['authors'] == ['Автор']
    assert found[0]['cover_url'] == 'https://cdn.litres.ru/pub/c/cover_415/5'


@pytest.mark.parametrize('audio_fields', [
    pytest.param({'art_type': 4}, id='audiobook-type'),
    pytest.param({'art_type': 10}, id='audio-type-10'),
    pytest.param({'url': '/audiobook/1'}, id='audiobook-url'),
    pytest.param({'url': '/podcast/1'}, id='podcast-url'),
])
def test_litres_audio_penalty_precedes_source_bonus(source, monkeypatch, log, audio_fields):
    # Exact title alone 80 - audio penalty 20 = 60, passes the 55 filter.
    # The LitRes bonus +5 is applied afterwards, giving a final score of 65.
    monkeypatch.setattr(source.transport, 'fetch_json', Mock(return_value={'payload': {'data': [
        {'id': 1, 'title': 'Книга', **audio_fields}]}}))
    assert [(c['id'], c['score']) for c in source.litres.search_litres(log, 'Книга', [], 7)] == [('1', 65)]


@pytest.mark.parametrize('base_score, expected', [
    pytest.param(54, [], id='54-rejected'),
    pytest.param(55, [('1', 60)], id='55-accepted-plus-five'),
    pytest.param(56, [('1', 61)], id='56-accepted-plus-five'),
])
def test_litres_score_filter_accepts_55_and_above(
        source, plugin_module, monkeypatch, log, base_score, expected):
    # Isolate the acceptance boundary from title/author scoring (tested separately).
    monkeypatch.setattr(litres, 'score_match', Mock(return_value=base_score))
    monkeypatch.setattr(source.transport, 'fetch_json', Mock(return_value={
        'payload': {'data': [litres_item(1)]}}))
    found = source.litres.search_litres(log, 'Книга', ['Автор'], 7)
    assert [(c['id'], c['score']) for c in found] == expected


def test_litres_no_title(source, monkeypatch, log):
    fetch = Mock()
    monkeypatch.setattr(source.transport, 'fetch_json', fetch)
    assert source.litres.search_litres(log, None, ['Автор'], 7) == []
    fetch.assert_not_called()


def test_litres_search_error_continues(source, monkeypatch, log):
    monkeypatch.setattr(source.transport, 'fetch_json', Mock(side_effect=[
        OSError('unavailable'), {'payload': {'data': [litres_item(1)]}}]))
    assert [c['id'] for c in source.litres.search_litres(log, 'Книга', ['Автор'], 7)] == ['1']


@pytest.mark.parametrize('payload', [
    pytest.param({'payload': {'data': {'id': 1, 'title': 'Подробное'}}}, id='nested-data'),
    pytest.param({'payload': {'id': 1, 'title': 'Подробное'}}, id='flat-payload'),
])
def test_fetch_litres_details(source, monkeypatch, log, payload):
    fetch = Mock(return_value=payload)
    monkeypatch.setattr(source.transport, 'fetch_json', fetch)
    mi = source.litres.fetch_litres_book(log, {'id': '1', 'title': 'Запасное'}, 7)
    assert mi.title == 'Подробное'
    assert mi.identifiers == {'litres': '1'}
    fetch.assert_called_once_with('https://api.litres.ru/foundation/api/arts/1', 7)


def test_fetch_litres_no_id(source, monkeypatch, log):
    fetch = Mock()
    monkeypatch.setattr(source.transport, 'fetch_json', fetch)
    assert source.litres.fetch_litres_book(log, {'title': 'Запасное'}, 7).title == 'Запасное'
    fetch.assert_not_called()


def test_fantlab_search(source, monkeypatch, log):
    def item(identifier, title='Книга', author='Автор', kind='work'):
        return {'id': identifier, 'url': 'https://api.fantlab.ru/work%s' % identifier,
                'name': title, 'type': kind, 'creators': {'authors': [{'name': author}]},
                'description': 'Аннотация', 'stat': {'rating': 8.5}, 'image': '/image.jpg',
                'name_type': 'Роман'}
    payload = {'works': [item(1, kind='edition'), item(2), item(3, 'Иное', 'Другой')]}
    monkeypatch.setattr(source.transport, 'fetch_url', Mock(return_value=json.dumps(payload)))
    found = source.fantlab.search_fantlab(log, 'Книга', ['Автор'], 7)
    assert [(c['id'], c['score']) for c in found] == [(2, 140), (1, 130)]
    assert found[0] == {'source': 'fantlab', 'score': 140, 'title': 'Книга',
        'authors': ['Автор'], 'id': 2, 'identifier': 'work2', 'url': 'https://fantlab.ru/work2',
        'comments': 'Аннотация', 'rating': 8.5, 'cover_url': 'https://api.fantlab.ru/image.jpg', 'tags': ['Роман']}


@pytest.mark.parametrize('response', [
    pytest.param(OSError('unavailable'), id='transport-error'),
    pytest.param('invalid json', id='invalid-json'),
])
def test_fantlab_errors(source, monkeypatch, log, response):
    fetch = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
    monkeypatch.setattr(source.transport, 'fetch_url', fetch)
    assert source.fantlab.search_fantlab(log, 'Книга', ['Автор'], 7) == []


def test_fantlab_empty_query(source, monkeypatch, log):
    fetch = Mock()
    monkeypatch.setattr(source.transport, 'fetch_url', fetch)
    assert source.fantlab.search_fantlab(log, None, None, 7) == []
    fetch.assert_not_called()
