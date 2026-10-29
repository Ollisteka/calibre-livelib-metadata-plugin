
import json
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('as_bytes', [False, True])
@pytest.mark.parametrize('method', ['fetch_url', 'fetch_json'])
def test_transport_contract(source, plugin_module, monkeypatch, as_bytes, method):
    body = '{"name": "Книга"}'
    response = Mock()
    response.read.return_value = body.encode() if as_bytes else body
    opener = Mock(return_value=response)
    monkeypatch.setattr(plugin_module, 'urlopen', opener)
    result = getattr(source, method)('https://example.invalid/data', 7)
    assert result == (json.loads(body) if method == 'fetch_json' else body)
    request = opener.call_args.args[0]
    assert opener.call_args.kwargs == {'timeout': 7}
    headers = dict((k.lower(), v) for k, v in request.header_items())
    assert headers['user-agent'] == plugin_module.USER_AGENT
    assert headers['accept-language'] == 'ru-RU,ru;q=0.9,en;q=0.7'
    if method == 'fetch_json':
        assert headers['referer'] == 'https://www.litres.ru/'
        assert headers['accept-version'] == '2'
        assert headers['accept'] == 'application/json,text/plain,*/*'
    else:
        assert headers['referer'] == 'https://www.livelib.ru/'
        assert 'accept-version' not in headers
        assert headers['accept'] == 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


def test_next_payload_and_balanced_json(plugin_module):
    payload = json.dumps({'nested': {'text': 'braces } { and "quoted"'}, 'list': [1]})
    raw = '<script>self.__next_f.push([1,%s])</script>' % json.dumps(payload)
    decoded = plugin_module.decode_next_payload(raw)
    assert decoded == payload
    assert json.loads(plugin_module.extract_balanced_json('prefix ' + decoded, 0)) == json.loads(payload)
    assert plugin_module.extract_balanced_json('{"open": {', 0) is None
    assert plugin_module.extract_balanced_json('none', 0) is None


def test_full_livelib_detail(source, plugin_module, monkeypatch, log):
    book = {'@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'},
            'isbn': 'raw-isbn', 'description': '<Текст>\nСтрока', 'genre': ['Роман'],
            'aggregateRating': {'ratingValue': '4.5', 'ratingCount': 12},
            'image': 'https://cover/1'}
    raw = '<script type="application/ld+json">%s</script>' % json.dumps([book])
    raw += '<div>Издательство: Издатель Год издания: 2020 Язык: Русский Подробная информация</div>'
    fetch = Mock(return_value=raw)
    isbn = Mock(return_value='validated-isbn')
    monkeypatch.setattr(source, 'fetch_url', fetch)
    monkeypatch.setattr(plugin_module, 'check_isbn', isbn)
    mi = source.fetch_book(log, 'https://www.livelib.ru/book/1', 7)
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