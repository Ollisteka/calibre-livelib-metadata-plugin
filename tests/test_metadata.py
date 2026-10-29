from plugin_under_test.providers.livelib import formatting
from plugin_under_test.providers.livelib import parsers

import pytest


@pytest.mark.parametrize('value, expected', [(None, None), ('bad', None), ('4,5', 4.5),
                                           (5, 5), (6, 3), (9, 4.5)],
                         ids=['missing', 'invalid', 'decimal-comma', 'five-unchanged',
                              'six-halved', 'nine-halved'])
def test_source_rating(plugin_module, value, expected):
    assert parsers.source_rating(value) == expected


@pytest.mark.parametrize('comments', [
    pytest.param('<p>Аннотация</p>', id='existing-annotation'),
    pytest.param(None, id='no-annotation'),
])
def test_empty_edition_details_preserve_comments(plugin_module, comments):
    assert formatting.append_edition_details(comments, {}) == comments


def test_edition_details_escape_values_and_append_to_annotation(plugin_module):
    comments = '<p>Аннотация</p>'
    assert formatting.append_edition_details(comments, {'publisher': '<Издатель & Co>', 'pages': '320'}) == (
        comments + '<p><b>Детали издания LiveLib:</b><br/>'
        'Издательство: &lt;Издатель &amp; Co&gt;<br/>Страниц: 320</p>')


@pytest.mark.parametrize('rating_count, expected', [
    pytest.param(12, '<p><b>Детали издания LiveLib:</b><br/>Год издания: 2020'
                 '<br/>Оценок LiveLib: 12</p>', id='positive-count-shown'),
    pytest.param(0, '<p><b>Детали издания LiveLib:</b><br/>Год издания: 2020</p>', id='zero-count-omitted'),
])
def test_edition_details_rating_count(plugin_module, rating_count, expected):
    assert formatting.append_edition_details(None, {'year': '2020'}, rating_count) == expected


def test_litres_metadata(source):
    item = {'id': 12, 'title': 'Книга', 'language_code': 'RU',
            'persons': [{'role': 'author', 'full_name': 'Автор'},
                        {'role': 'publisher', 'full_name': 'Издатель'}],
            'annotation': ' <b>Аннотация</b> ',
            'genres': [{'title': 'Роман'}, {'name': 'Проза'}], 'rating': {'rated_avg': '4.5'}}
    mi = source.litres.metadata_from_litres_candidate({}, item)
    assert (mi.title, mi.authors, mi.language, mi.publisher) == ('Книга', ['Автор'], 'rus', 'Издатель')
    assert mi.identifiers == {'litres': '12'}
    assert mi.comments == '<p><b>Аннотация</b></p>'
    assert mi.tags == ['Роман', 'Проза']
    assert mi.rating == 9
    assert mi.has_cover
    assert source.get_cached_cover_url(mi.identifiers) == 'https://cdn.litres.ru/pub/c/cover_415/12'


@pytest.mark.parametrize('rating, expected', [(5, 10), (8, 8), ('bad', None), (None, None)],
                         ids=['five-doubled', 'eight-unchanged', 'invalid-rating', 'missing-rating'])
def test_litres_fallbacks_and_rating(source, rating, expected):
    mi = source.litres.metadata_from_litres_candidate({'title': 'Запасное', 'authors': ['Автор'],
                                               'raw': {'rating': rating}})
    assert (mi.title, mi.authors) == ('Запасное', ['Автор'])
    assert mi.rating == expected
    assert mi.comments is None
    assert mi.identifiers == {}
    assert not mi.has_cover
    assert mi.language is None


@pytest.mark.parametrize('item', [
    pytest.param({'description': 'Описание'}, id='description'),
    pytest.param({'meta_tags': {'root': {'open_graph_description': 'Описание'}}}, id='open-graph-description'),
    pytest.param({'meta_tags': {'root': {'description': 'Описание'}}}, id='root-meta-description'),
])
def test_litres_description_fallbacks(source, item):
    mi = source.litres.metadata_from_litres_candidate({}, item)
    assert mi.comments == '<p>Описание</p>'
    assert mi.authors == ['Unknown']


def test_litres_tag_limit(source):
    mi = source.litres.metadata_from_litres_candidate({}, {'genres_hierarchy': ['Жанр %s' % i for i in range(10)]})
    assert mi.tags == ['Жанр %s' % i for i in range(8)]


@pytest.mark.parametrize('rating, expected', [('4.5', 9), ('bad', None), (None, None)],
                         ids=['rating-doubled', 'invalid-rating', 'missing-rating'])
def test_livelib_candidate(source, rating, expected):
    mi = source.livelib.metadata_from_search_candidate({'title': 'Книга', 'author': 'Автор',
        'url': 'https://www.livelib.ru/book/123', 'rating': rating,
        'summary': 'Описание', 'cover_url': 'https://cover/123'})
    assert (mi.title, mi.authors, mi.language) == ('Книга', ['Автор'], 'rus')
    assert mi.identifiers == {'livelib': '123'}
    assert mi.comments == '<p>Описание</p>'
    assert mi.rating == expected
    assert source.get_cached_cover_url(mi.identifiers) == 'https://cover/123'


def test_livelib_missing_fields(source):
    assert source.livelib.metadata_from_search_candidate({}) is None
    mi = source.livelib.metadata_from_search_candidate({'title': 'Книга', 'url': '/book/1'})
    assert mi.authors == ['Unknown']
    assert mi.comments is None


@pytest.mark.parametrize('rating, expected', [('8.5', 8.5), ('bad', None), (None, None)],
                         ids=['rating-unchanged', 'invalid-rating', 'missing-rating'])
def test_fantlab_metadata(source, rating, expected):
    mi = source.fantlab.metadata_from_fantlab_candidate({'title': 'Книга', 'authors': ['Автор'],
        'identifier': 'work12', 'id': 12, 'comments': 'Один\nДва', 'rating': rating,
        'tags': ['Роман'], 'cover_url': 'https://cover/12'})
    assert (mi.title, mi.authors, mi.language) == ('Книга', ['Автор'], 'rus')
    assert mi.identifiers == {'fantlab': 'work12'}
    assert mi.comments == '<p>Один<br/>Два</p>'
    assert mi.rating == expected
    assert mi.tags == ['Роман']
    assert mi.has_cover
    assert source.get_cached_cover_url(mi.identifiers) == 'https://cover/12'


def test_fantlab_missing_fields(source):
    mi = source.fantlab.metadata_from_fantlab_candidate({})
    assert (mi.title, mi.authors, mi.language) == ('', ['Unknown'], 'rus')
    assert mi.comments is None
    assert mi.identifiers == {}
    assert not mi.has_cover
