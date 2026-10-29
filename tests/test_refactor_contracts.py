from plugin_under_test import constants
from plugin_under_test import html_utils
from plugin_under_test.providers.livelib import parsers
from plugin_under_test.providers.livelib import provider
from plugin_under_test import transport

import json
from unittest.mock import Mock, MagicMock

import pytest


@pytest.mark.parametrize('as_bytes', [False, True])
@pytest.mark.parametrize('method', ['fetch_livelib_text', 'fetch_litres_json', 'fetch_fantlab_json'])
def test_transport_contract(source, monkeypatch, as_bytes, method):
    body = '{"name": "Книга"}'
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = body.encode() if as_bytes else body
    opener = Mock(return_value=response)
    monkeypatch.setattr(transport, 'urlopen', opener)
    result = getattr(source.transport, method)('https://example.invalid/data', 7)
    assert result == (json.loads(body) if method != 'fetch_livelib_text' else body)
    response.__exit__.assert_called_once()
    request = opener.call_args.args[0]
    assert opener.call_args.kwargs == {'timeout': 7}
    headers = dict((k.lower(), v) for k, v in request.header_items())
    assert headers['user-agent'] == constants.USER_AGENT
    assert headers['accept-language'] == 'ru-RU,ru;q=0.9,en;q=0.7'
    if method == 'fetch_litres_json':
        assert headers['referer'] == 'https://www.litres.ru/'
        assert headers['accept-version'] == '2'
        assert headers['accept'] == 'application/json,text/plain,*/*'
    elif method == 'fetch_fantlab_json':
        assert headers['referer'] == 'https://fantlab.ru/'
        assert 'accept-version' not in headers
    else:
        assert headers['referer'] == 'https://www.livelib.ru/'
        assert 'accept-version' not in headers
        assert headers['accept'] == 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


def test_next_payload_and_balanced_json():
    payload = json.dumps({'nested': {'text': 'braces } { and "quoted"'}, 'list': [1]})
    raw = '<script>self.__next_f.push([1,%s])</script>' % json.dumps(payload)
    decoded = parsers.decode_next_payload(raw)
    assert decoded == payload
    assert json.loads(html_utils.extract_balanced_json('prefix ' + decoded, 0)) == json.loads(payload)
    assert html_utils.extract_balanced_json('{"open": {', 0) is None
    assert html_utils.extract_balanced_json('none', 0) is None


def test_full_livelib_detail(source, monkeypatch, log):
    book = {'@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'},
            'isbn': 'raw-isbn', 'description': '<Текст>\nСтрока', 'genre': ['Роман'],
            'aggregateRating': {'ratingValue': '4.5', 'ratingCount': 12},
            'image': 'https://cover/1'}
    raw = '<script type="application/ld+json">%s</script>' % json.dumps([book])
    raw += '<div>Издательство: Издатель Год издания: 2020 Язык: Русский Подробная информация</div>'
    fetch = Mock(return_value=raw)
    isbn = Mock(return_value='validated-isbn')
    monkeypatch.setattr(source.transport, 'fetch_livelib_text', fetch)
    monkeypatch.setattr(provider, 'check_isbn', isbn)
    mi = source.livelib.fetch_book(log, 'https://www.livelib.ru/book/1', 7)
    fetch.assert_called_once_with('https://beta.livelib.ru/book/1', 7)
    isbn.assert_called_once_with('raw-isbn')
    assert (mi.title, mi.authors, mi.language, mi.publisher) == ('Книга', ['Автор'], 'rus', 'Издатель')
    assert mi.isbn == 'validated-isbn'
    assert mi.pubdate.year == 2020
    assert mi.tags == ['Роман']
    assert mi.rating == 9
    assert '<p>&lt;Текст&gt;<br/>Строка</p>' in mi.comments
    assert 'Оценок LiveLib: 12' in mi.comments
    assert mi.has_cover
    assert source.get_cached_cover_url(mi.identifiers) == 'https://cover/1'
