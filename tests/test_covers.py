from unittest.mock import Mock

import pytest


PREVIEW = 'https://s1.livelib.ru/boocover/123/200x300/ab/cover.jpg'
ORIGINAL = 'https://s1.livelib.ru/boocover/123/o/ab/cover.jpeg'


@pytest.mark.parametrize('url, original, candidates', [
    (PREVIEW, ORIGINAL, [ORIGINAL, PREVIEW]),
    (ORIGINAL, None, [ORIGINAL]), ('https://elsewhere/cover.png', None, ['https://elsewhere/cover.png']),
    ('', None, []), (None, None, []),
], ids=['preview-expanded', 'original-unchanged', 'other-source-unchanged', 'empty', 'missing'])
def test_cover_variants(plugin_module, url, original, candidates):
    assert plugin_module.livelib_original_cover_url(url) == original
    assert plugin_module.livelib_cover_candidates(url) == candidates


@pytest.mark.parametrize('url, art_id, expected', [
    ('//cdn.example/1', None, 'https://cdn.example/1'),
    ('/pub/1', None, 'https://cdn.litres.ru/pub/1'),
    ('/cover/1', None, 'https://www.litres.ru/cover/1'),
    ('https://cover/1', None, 'https://cover/1'),
    (None, None, None), ('', None, None),
    ('https://preview/1', '12', 'https://cdn.litres.ru/pub/c/cover_415/12'),
], ids=['protocol-relative', 'cdn-relative', 'site-relative', 'absolute', 'missing',
        'empty', 'art-id-overrides-preview'])
def test_litres_cover(source, url, art_id, expected):
    assert source.absolutize_litres_cover(url, art_id) == expected


@pytest.mark.parametrize('kind', ['litres', 'livelib', 'fantlab'])
def test_cache(source, kind):
    assert source.get_cached_cover_url({kind: '1'}) is None
    source.cache_identifier_to_cover_url('1', 'https://cover/1')
    assert source.get_cached_cover_url({kind: '1'}) == 'https://cover/1'
    assert source.get_cached_cover_url(None) is None


def test_cache_priority(source):
    for identifier in ['1', '2', 'work3']:
        source.cache_identifier_to_cover_url(identifier, 'https://cover/' + identifier)
    assert source.get_cached_cover_url({'litres': '1', 'livelib': '2', 'fantlab': 'work3'}) == 'https://cover/1'
    assert source.get_cached_cover_url({'livelib': '2', 'fantlab': 'work3'}) == 'https://cover/2'


def test_collect_covers(source, plugin_module, monkeypatch, log, abort):
    source.cache_identifier_to_cover_url('initial', 'https://cover/cached')
    def identify(log, queue, abort, **kwargs):
        for identifier, url in [('1', 'https://cover/one'), ('2', 'https://cover/cached'),
                                ('3', 'https://cover/three'), ('4', None)]:
            mi = plugin_module.Metadata('Книга', ['Автор'])
            mi.set_identifier('litres', identifier)
            source.cache_identifier_to_cover_url(identifier, url)
            queue.put(mi)
    monkeypatch.setattr(source, 'identify', identify)
    direct = Mock(side_effect=AssertionError('No fallback when covers exist'))
    monkeypatch.setattr(source, 'find_cover_url_direct', direct)
    assert source.find_all_cover_urls(log, abort, 'Книга', [], {'litres': 'initial'}, 7) == [
        'https://cover/cached', 'https://cover/one', 'https://cover/three']
    direct.assert_not_called()


def test_cover_direct_fallback(source, monkeypatch, log, abort):
    monkeypatch.setattr(source, 'identify', Mock())
    direct = Mock(return_value='https://cover/direct')
    monkeypatch.setattr(source, 'find_cover_url_direct', direct)
    assert source.find_all_cover_urls(log, abort, 'Книга', [], {}, 7) == ['https://cover/direct']
    direct.assert_called_once_with(log, title='Книга', authors=[], timeout=7)


def test_no_cover_query(source, monkeypatch, log, abort):
    identify = Mock()
    direct = Mock()
    monkeypatch.setattr(source, 'identify', identify)
    monkeypatch.setattr(source, 'find_cover_url_direct', direct)
    assert source.find_all_cover_urls(log, abort, None, None, {}, 7) == []
    identify.assert_not_called()
    direct.assert_not_called()


@pytest.mark.parametrize('urls, expected', [
    pytest.param([PREVIEW, ORIGINAL, 'https://other/cover'],
                 [ORIGINAL, PREVIEW, 'https://other/cover'], id='deduplicated-cover-variants'),
    pytest.param([], [], id='no-covers-no-download'),
])
def test_download_handoff(source, monkeypatch, log, abort, results, urls, expected):
    monkeypatch.setattr(source, 'find_all_cover_urls', Mock(return_value=urls))
    downloader = Mock()
    monkeypatch.setattr(source, 'download_multiple_covers', downloader)
    source.download_cover(log, results, abort, title='Книга', authors=['Автор'], timeout=7, get_best_cover=True)
    if expected:
        downloader.assert_called_once_with('Книга', ['Автор'], expected, True, 7, results, abort, log, prefs_name=None)
    else:
        downloader.assert_not_called()
