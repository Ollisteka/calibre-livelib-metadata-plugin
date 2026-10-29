from plugin_under_test import identifiers

import pytest


@pytest.mark.parametrize('url', [
    'https://www.livelib.ru/book/123',
    'https://beta.livelib.ru/book/123?x=1#details', '/book/123#details',
], ids=['main-site', 'beta-query-and-fragment', 'relative-with-fragment'])
def test_livelib_urls(plugin_module, source, url):
    assert identifiers.livelib_id_from_url(url) == '123'
    assert identifiers.livelib_beta_url(url) == 'https://beta.livelib.ru/book/123'


@pytest.mark.parametrize('url, expected', [
    ('https://fantlab.ru/work123?x=1#abc', 'work123'),
    ('https://api.fantlab.ru/edition42/', 'edition42'),
    ('https://elsewhere.ru/work123', None), ('https://fantlab.ru/123', None),
    ('https://fantlab.ru/work', None), ('https://fantlab.ru/work1/extra', None),
    ('', None), (None, None),
], ids=['work-query-and-fragment', 'api-edition', 'foreign-domain', 'numeric-only',
        'missing-number', 'nested-path', 'empty', 'missing'])
def test_fantlab_identifier(plugin_module, url, expected):
    assert identifiers.fantlab_identifier_from_url(url) == expected


@pytest.mark.parametrize('identifiers, expected', [
    ({'litres': '1', 'livelib': '2', 'fantlab': 'work3'},
     ('litres', '1', 'https://www.litres.ru/book/1')),
    ({'livelib': '2', 'fantlab': 'work3'}, ('livelib', '2', 'https://www.livelib.ru/book/2')),
    ({'fantlab': 'work3'}, ('fantlab', 'work3', 'https://fantlab.ru/work3')),
    ({'fantlab': '123'}, None), ({'isbn': '9785170906309'}, None), ({}, None),
], ids=['litres-priority', 'livelib-priority', 'fantlab-resource-path',
        'invalid-fantlab-id', 'unsupported-id', 'no-identifiers'])
def test_book_url(source, identifiers, expected):
    assert source.get_book_url(identifiers) == expected


@pytest.mark.parametrize('kind, name', [('litres', 'Litres'), ('livelib', 'LiveLib'),
                                       ('fantlab', 'FantLab'), ('other', 'LiveLib Metadata')])
def test_source_names(source, kind, name):
    assert source.get_book_url_name(kind, '123', '') == name


def test_id_from_url(source):
    assert source.id_from_url('https://beta.livelib.ru/book/123?x=1#abc') == ('livelib', '123')
    assert source.id_from_url('https://fantlab.ru/work123') is None
    assert source.id_from_url(None) is None


def test_id_from_url_currently_accepts_lookalike_domain(source):
    # Characterize existing behavior until hostname validation is fixed.
    # TODO: Restrict URLs to supported LiveLib hostnames, then expect None here.
    assert source.id_from_url('https://notlivelib.ru/book/123') == ('livelib', '123')
