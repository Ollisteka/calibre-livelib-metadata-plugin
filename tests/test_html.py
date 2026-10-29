from plugin_under_test import html_utils
from plugin_under_test.providers.livelib import parsers

import json

import pytest


@pytest.mark.parametrize('graph', [False, True], ids=['standalone-book', 'book-in-graph'])
def test_json_ld_book(plugin_module, graph):
    book = {'@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'}, 'isbn': '9785170906309'}
    payload = {'@graph': [{'@type': 'WebSite'}, book]} if graph else book
    raw = '<script type="application/ld+json">%s</script>' % json.dumps(payload)
    assert parsers.extract_livelib_json(raw) == book


def test_broken_json(plugin_module):
    assert parsers.extract_livelib_json('<script type="application/ld+json">{broken</script>') is None


def test_edition_text(plugin_module):
    raw = ('<div>Издательство: Издатель ISBN: 9785170906309 Год издания: 2020 '
           'Язык: Русский Количество страниц - 320 Возрастные ограничения: 16+ Содержание</div>')
    assert parsers.extract_livelib_page_details(raw) == {
        'publisher': 'Издатель', 'isbn': '9785170906309', 'year': '2020',
        'language': 'Русский', 'pages': '320', 'physical': '320 стр.', 'age': '16+'}
    assert parsers.extract_livelib_page_details('<div>Обычный текст</div>') == {}


CARD = '''<div class="object-edition">
 <div class="brow-title"><a class="title" href="/book/123">Книга</a></div>
 <a class="description">Автор</a><span itemprop="ratingValue">4.5</span></div>'''


def test_legacy_card_and_duplicates(source):
    assert parsers.parse_search_results(CARD + CARD, 'Книга', ['Автор']) == [{
        'source': 'livelib', 'score': 140, 'url': 'https://www.livelib.ru/book/123',
        'title': 'Книга', 'author': 'Автор', 'rating': '4.5', 'cover_url': None}]


def test_legacy_card_below_matching_threshold(source):
    assert parsers.parse_search_results(CARD, 'Другая книга', ['Чужой']) == []


def test_clean_html(plugin_module):
    assert html_utils.clean_html('<div>Книга&nbsp;\x01 автора</div>') == '<div>Книга&nbsp; автора</div>'
    assert html_utils.clean_html(None) == ''


def test_compact_text(plugin_module):
    assert html_utils.compact_page_text('<div>Книга&nbsp;\x01 автора</div>') == 'Книга автора'
