import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from offline_support import UnexpectedNetwork
from plugin_under_test import LiveLibMetadata, transport
from plugin_under_test.identify import identify
from plugin_under_test.providers.livelib import parsers, provider


def test_instances_do_not_share_cache_or_dependencies(source):
    other = LiveLibMetadata()
    source.cache_identifier_to_cover_url('1', 'https://cover/1')
    assert other.get_cached_cover_url({'litres': '1'}) is None
    for name in ('transport', 'litres', 'livelib', 'fantlab', 'covers'):
        assert getattr(source, name) is not getattr(other, name)


def test_identify_never_requests_cover_bytes(source, monkeypatch, log, results, abort):
    requested = []
    def open_request(request, timeout):
        requested.append(request.full_url)
        if request.full_url != 'https://api.litres.ru/foundation/api/arts/123':
            raise UnexpectedNetwork('Image or unexpected request during identify')
        return SimpleNamespace(read=lambda: json.dumps({'payload': {'data': {
            'id': 123, 'title': 'Книга', 'cover_url': 'https://cover/image.jpg'}}}).encode())
    monkeypatch.setattr(transport, 'urlopen', open_request)
    source.identify(log, results, abort, identifiers={'litres': '123'})
    assert len(requested) == 1
    assert results.get_nowait().has_cover
    assert source.get_cached_cover_url({'litres': '123'}) == 'https://cdn.litres.ru/pub/c/cover_415/123'


def test_next_search_payload_is_parsed_without_source():
    item = {'url': '/book/123', 'title': 'Книга', 'authors': [{'full_name': 'Автор'}],
            'cover_url': '/cover.jpg', 'stats': {'rating': '9'}}
    data = {'payload': {'data': [{'type': 'art_editions', 'instance': item}] * 2}}
    payload = '"searchData":' + json.dumps(data)
    raw = '<script>self.__next_f.push([1,%s])</script>' % json.dumps(payload)
    assert parsers.parse_search_results(raw, 'Книга', ['Автор']) == [{
        'source': 'livelib', 'score': 148, 'url': 'https://beta.livelib.ru/book/123',
        'title': 'Книга', 'author': 'Автор', 'cover_url': 'https://beta.livelib.ru/cover.jpg',
        'rating': '4.5'}]


def test_search_parser_errors_still_propagate(source, monkeypatch, log):
    monkeypatch.setattr(source.transport, 'fetch_url', Mock(return_value='html'))
    monkeypatch.setattr(provider, 'parse_search_results', Mock(side_effect=ValueError('parse')))
    with pytest.raises(ValueError, match='parse'):
        source.livelib.search_page('https://example.invalid', 'Книга', [], 7, log=log)


def test_identify_with_explicit_fake_providers(log, results, abort):
    calls = []
    def search(name, rows):
        def run(*args, **kwargs):
            calls.append(name)
            return rows
        return run
    first = SimpleNamespace(source_relevance=None)
    second = SimpleNamespace(source_relevance=None)
    litres = SimpleNamespace(search_litres=search('litres', [{'source': 'litres', 'score': 100}]),
                              fetch_litres_book=lambda *args: first)
    livelib = SimpleNamespace(search_page=search('beta', []))
    fantlab = SimpleNamespace(search_fantlab=search('fantlab', [{'source': 'fantlab', 'score': 100}]),
                              metadata_from_fantlab_candidate=lambda row: second)
    identify(litres, livelib, fantlab, Mock(), log, results, abort, title='Книга')
    assert calls == ['litres', 'beta', 'fantlab']
    assert [results.get_nowait(), results.get_nowait()] == [first, second]
    assert first.source_relevance == second.source_relevance == -100


def test_higher_priority_cache_miss_does_not_use_lower_source(source):
    source.cache_identifier_to_cover_url('2', 'https://cover/2')
    assert source.get_cached_cover_url({'litres': '1', 'livelib': '2'}) is None
