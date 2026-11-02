"""Regression tests use a shared clock rather than sleeping or network access."""
import importlib
import json
from unittest.mock import Mock

import pytest

from plugin_under_test.providers import litres


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(importlib.import_module('plugin_under_test.identify'), 'monotonic', lambda: now[0])
    monkeypatch.setattr(litres, 'monotonic', lambda: now[0])
    return now


def test_litres_does_not_retry_after_its_budget_expires(source, monkeypatch, log, clock):
    def timeout(url, remaining):
        clock[0] += remaining
        raise TimeoutError('TLS handshake timed out')
    fetch = Mock(side_effect=timeout)
    monkeypatch.setattr(source.transport, 'fetch_litres_json', fetch)
    assert source.litres.search_litres(log, 'Книга', ['Автор'], 7) == []
    assert fetch.call_count == 1
    assert clock[0] == 7


def test_litres_retry_uses_only_remaining_time(source, monkeypatch, log, clock):
    budgets = []
    def fetch(url, remaining):
        budgets.append(remaining)
        clock[0] += 2
        if len(budgets) == 1:
            raise OSError('connection failed')
        return {'payload': {'data': []}}
    monkeypatch.setattr(source.transport, 'fetch_litres_json', fetch)
    source.litres.search_litres(log, 'Книга', ['Автор'], 7)
    assert budgets == [7, 5]


@pytest.mark.parametrize('fantlab_enabled', [False, True])
def test_litres_timeout_leaves_time_for_livelib_and_details(
        source, monkeypatch, log, results, abort, clock, fantlab_enabled):
    source.prefs['use_fantlab'] = fantlab_enabled
    calls = []
    def litres_timeout(url, remaining):
        calls.append('litres')
        clock[0] += remaining
        raise TimeoutError('TLS handshake timed out')
    def html(url, remaining):
        assert remaining > 0
        if '/search?' in url:
            calls.append('beta')
            clock[0] += remaining
            raise TimeoutError('beta unavailable')
        if '/find/' in url:
            calls.append('legacy')
            clock[0] += 1
            data = {'payload': {'data': [{'type': 'art_editions', 'instance': {
                'url': '/book/1016105470', 'title': 'Книга',
                'authors': [{'full_name': 'Автор'}]}}]}}
            return '<script>self.__next_f.push([1,%s])</script>' % json.dumps(
                '"searchData":' + json.dumps(data))
        calls.append('details')
        clock[0] += 1
        return '<script type="application/ld+json">%s</script>' % json.dumps({
            '@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'},
            'description': 'Описание'})
    monkeypatch.setattr(source.transport, 'fetch_litres_json', litres_timeout)
    monkeypatch.setattr(source.transport, 'fetch_livelib_text', html)
    from plugin_under_test.providers.livelib import provider
    monkeypatch.setattr(provider, 'check_isbn', lambda value: None)
    def fantlab_timeout(*args, timeout):
        calls.append('fantlab')
        clock[0] += timeout
        return []
    monkeypatch.setattr(source.fantlab, 'search_fantlab', fantlab_timeout)
    source.identify(log, results, abort, title='Книга', authors=['Автор'], timeout=30)
    assert calls == ['litres', 'beta', 'legacy'] + (['fantlab'] if fantlab_enabled else []) + ['details']
    mi = results.get_nowait()
    assert mi.identifiers == {'livelib': '1016105470'}
    assert mi.comments == '<p>Описание</p>'
    assert clock[0] < 30


def test_slow_detail_leaves_time_for_next_candidate(source, monkeypatch, log, results, abort, clock):
    source.prefs.update(use_livelib=False, use_fantlab=False)
    rows = [{'source': 'litres', 'score': 140 - i, 'id': str(i),
             'title': 'Книга', 'authors': ['Автор']} for i in (1, 2)]
    monkeypatch.setattr(source.litres, 'search_litres', lambda *args, **kwargs: rows)
    fetched = []
    def details(log, row, timeout):
        fetched.append(row['id'])
        if row['id'] == '1':
            clock[0] += timeout
            raise TimeoutError('details timed out')
        assert timeout > 0
        return source.litres.metadata_from_litres_candidate(row)
    monkeypatch.setattr(source.litres, 'fetch_litres_book', details)
    source.identify(log, results, abort, title='Книга', timeout=30)
    assert fetched == ['1', '2']
    assert results.qsize() == 2


def test_expired_search_does_not_log_unrequested_livelib_urls(
        source, monkeypatch, results, abort, clock):
    log = Mock()
    def stalled(*args, **kwargs):
        clock[0] = 31
        return []
    monkeypatch.setattr(source.litres, 'search_litres', stalled)
    source.identify(log, results, abort, title='Книга', timeout=30)
    assert not any('LiveLib search:' in str(call) for call in log.info.call_args_list)


@pytest.mark.parametrize('known_second', [False, True])
def test_slow_direct_leaves_time_for_other_sources(source, monkeypatch, log, results, abort, clock, known_second):
    source.prefs['use_fantlab'] = False
    def slow(log, row, timeout):
        clock[0] += timeout
        raise TimeoutError('direct timeout')
    monkeypatch.setattr(source.litres, 'fetch_litres_book', slow)
    calls = []
    def complete(log, row, timeout):
        assert timeout > 0
        calls.append('details')
        from calibre.ebooks.metadata.book.base import Metadata
        mi = Metadata('Book', ['Author'])
        mi.set_identifier('livelib', '2')
        return mi
    def search(*args, timeout, **kwargs):
        assert timeout > 0
        calls.append('search')
        return [dict(source='livelib', score=140, url='https://beta.livelib.ru/book/2', title='Book', author='Author')]
    monkeypatch.setattr(source.livelib, 'complete_candidate', complete)
    monkeypatch.setattr(source.livelib, 'search_page', search)
    ids = {'litres': '1'}
    if known_second:
        ids['livelib'] = '2'
    source.identify(log, results, abort, title='Book', authors=['Author'], identifiers=ids, timeout=30)
    assert calls == (['details'] if known_second else ['search', 'details'])
    assert not results.empty()
