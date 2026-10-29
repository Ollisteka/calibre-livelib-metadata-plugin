from plugin_under_test import matching

import pytest


@pytest.mark.parametrize('value, expected', [
    (None, ''), ('', ''), ('  ЁЖ_и—Ель!!  ', 'еж и ель'),
    ('КНИГА\t  автора', 'книга автора'),
], ids=['none', 'empty', 'yo-punctuation-and-underscores', 'case-and-whitespace'])
def test_norm(plugin_module, value, expected):
    assert matching.norm(value) == expected


@pytest.mark.parametrize('query_title, query_authors, title, author, expected', [
    # Exact title 80 + exact author 60 = 140.
    pytest.param('Книга', ['Автор'], 'Книга', 'Автор', 140, id='exact-title-and-author'),
    # Partial title 45 + partial author 35 = 80.
    pytest.param('Книга', ['Автор'], 'Книга вторая', 'Автор Иванов', 80, id='partial-title-and-author'),
    # First three title tokens found out of order contribute 30.
    pytest.param('Север юг запад', [], 'запад север и юг', '', 30, id='reordered-title-tokens'),
    # Exact title 80 + one shared author token 10 = 90.
    pytest.param('Книга', ['Иван Петров'], 'Книга', 'Пётр Петров', 90, id='shared-author-token'),
    pytest.param('Книга', ['Автор'], 'Иное', 'Другой', 0, id='unrelated-title-and-author'),
    pytest.param(None, None, 'Книга', 'Автор', 0, id='empty-query'),
    pytest.param('Книга', [], 'Книга', '', 80, id='exact-title-without-author'),
    pytest.param('', ['Автор'], '', 'Автор', 60, id='exact-author-without-title'),
])
def test_scores(plugin_module, query_title, query_authors, title, author, expected):
    assert matching.score_match(query_title, query_authors, title, author) == expected


@pytest.mark.parametrize('query, title, expected', [
    ('Книга', 'КНИГА', True), ('Книга', 'Книга вторая', True),
    ('Север юг запад', 'юг и север', True),
    ('Север юг запад', 'север восток', False),
    ('Книга', 'Другое', False), ('', 'Книга', False), ('Книга', None, False),
], ids=['exact-title', 'partial-title', 'two-shared-tokens', 'only-one-of-three-tokens',
        'unrelated-titles', 'empty-query', 'missing-result-title'])
def test_title_matching(plugin_module, query, title, expected):
    assert matching.title_match_enough(query, title) is expected


def test_title_matching_currently_accepts_no_shared_tokens(plugin_module):
    # Characterize existing behavior when the query has no multi-character tokens.
    # TODO: Return False when there are no matches, then expect False here.
    assert matching.title_match_enough('я', 'Дом') is True
