import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugin_under_test import transport
from plugin_under_test.providers.livelib import reading
from plugin_under_test.providers.livelib.formatting import append_edition_details, append_personal_details
from test_multiple_ids import setup_sources


def book(identifier='22', rating='4.5'):
    personal = ('' if rating is None else
                '<div class="brow-ratings">Оценка reader: '
                '<span class="rating-value">%s</span></div>' % rating)
    return ('<div class="book-item-manage" id="div-userbook-999">'
            '<a class="brow-book-name with-cycle" href="/book/%s-title">Книга</a>'
            '<div class="brow-cover"><span class="rating-value">4.99</span></div>%s'
            '<p id="book-22-full">Аннотация издателя, не личный отзыв</p></div>') % (identifier, personal)


def page(content, last=True):
    return {'error_code': 0, 'content': content, 'last_page': last}


HEADING = '<div class="brow-h2"><h2>Октябрь 2026 г.</h2></div>'


def test_parse_uses_personal_rating_and_preserves_date_precision():
    entries, date = reading.parse_read_page(HEADING + book())
    assert entries == {'22': {'rating': 4.5, 'read_date': 'Октябрь 2026 г.'}}
    assert date == 'Октябрь 2026 г.'


def test_work_links_do_not_match_edition_ids():
    entries, _ = reading.parse_read_page(HEADING + book().replace('/book/22-title', '/work/22-title'))
    assert entries == {}


def test_personal_details_do_not_extend_an_unrelated_final_paragraph():
    comments = append_edition_details(None, {'pages': '320'}) + '<p>Другая заметка</p>'
    result = append_personal_details(comments, {'rating': 4})
    assert result.startswith(comments)
    assert '<p>Другая заметка</p>' in result


@pytest.mark.parametrize('value, expected', [(None, None), ('—', None), ('0', None),
    ('6', None), ('NaN', None), ('inf', None), ('4,5', 4.5), ('5', 5)])
def test_absent_or_invalid_rating_never_uses_aggregate(value, expected):
    entries, _ = reading.parse_read_page(book(rating=value))
    assert entries == {'22': {} if expected is None else {'rating': expected}}


def test_dates_across_headers_pages_and_rereads():
    entries, date = reading.parse_read_page(HEADING + book() +
        '<div class="brow-h2"><h2>2025 г.</h2></div>' + book('22', '3') + book('33', None))
    assert entries['22']['rating'] == 4.5
    assert entries['22']['read_date'] == 'Октябрь 2026 г.'
    continued, _ = reading.parse_read_page(book('44', None), date)
    assert continued['44']['read_date'] == '2025 г.'


def test_paginated_lookup_cache_and_username_change(source, monkeypatch, log, abort):
    post = Mock(side_effect=[page(HEADING + book(), False), page(book('33')),
                            page(book('22', '2'))])
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    history = source.reading
    found = history.lookup('first', ['33-slug'], log, abort, 5)
    assert found['33']['read_date'] == 'Октябрь 2026 г.'
    assert [call.args[1]['page_no'] for call in post.call_args_list] == [1, 2]
    assert all(0 < call.args[2] <= 5 for call in post.call_args_list)
    assert history.lookup('first', ['22', '99'], log, abort, 5) == {
        '22': {'rating': 4.5, 'read_date': 'Октябрь 2026 г.'}}
    assert post.call_count == 2
    assert history.lookup('second', ['22'], log, abort, 5) == {'22': {'rating': 2}}
    assert post.call_count == 3


def test_partial_scan_resumes_and_first_found_book_is_cached(source, monkeypatch, log, abort):
    post = Mock(side_effect=[page(HEADING + book(), False), OSError('offline'), page(book('33'))])
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    assert source.reading.lookup('reader', ['22'], log, abort, 5)['22']['rating'] == 4.5
    assert post.call_count == 1
    assert source.reading.lookup('reader', ['33'], log, abort, 5) == {}
    assert source.reading.lookup('reader', ['33'], log, abort, 5)['33']['read_date'] == 'Октябрь 2026 г.'
    assert [c.args[1]['page_no'] for c in post.call_args_list] == [1, 2, 2]


def test_cache_expires(source, monkeypatch, log, abort):
    clock = Mock(return_value=10)
    monkeypatch.setattr(reading, 'monotonic', clock)
    post = Mock(side_effect=[page(book()), page(book(rating='3'))])
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    assert source.reading.lookup('reader', ['22'], log, abort, 5)['22']['rating'] == 4.5
    clock.return_value = 311
    assert source.reading.lookup('reader', ['22'], log, abort, 5)['22']['rating'] == 3


@pytest.mark.parametrize('response', [page('', False), {'error_code': 1},
    '<html>login</html>', {'content': 'challenge'}, page(book(), False)])
def test_bad_responses_and_repeated_page_stop(source, monkeypatch, log, abort, response):
    post = Mock(return_value=response)
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    assert source.reading.lookup('reader', ['99'], log, abort, 5) == {}
    assert post.call_count <= 2
    assert not source.reading._complete


@pytest.mark.parametrize('timeout, cancelled', [(0, False), (5, True)])
def test_no_requests_after_deadline_or_cancel(source, monkeypatch, log, abort, timeout, cancelled):
    if cancelled:
        abort.set()
    post = Mock()
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    assert source.reading.lookup('reader', ['22'], log, abort, timeout) == {}
    post.assert_not_called()


def test_timeout_preserves_progress_without_negative_cache(source, monkeypatch, log, abort):
    clock = Mock(return_value=0)
    monkeypatch.setattr(reading, 'monotonic', clock)
    def first(*args):
        clock.return_value = 6
        return page(HEADING + book(), False)
    post = Mock(side_effect=first)
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    assert source.reading.lookup('reader', ['33'], log, abort, 5) == {}
    assert post.call_count == 1
    assert source.reading._next_page == 2 and not source.reading._complete


def test_personal_rows_extend_one_edition_block_and_escape():
    comments = append_edition_details('<p>Аннотация</p>', {'pages': '320'})
    result = append_personal_details(comments, {'rating': 4.5, 'read_date': '<Дата> & год'})
    assert result.count('Детали издания LiveLib:') == 1
    assert 'Моя оценка LiveLib: 4,5 / 5' in result
    assert 'Дата прочтения LiveLib: &lt;Дата&gt; &amp; год' in result
    assert result.startswith('<p>Аннотация</p>')


@pytest.mark.parametrize('rating', [1, 2, 3, 3.5, 4, 4.5, 5])
def test_personal_metadata_applies_to_all_merged_results(source, monkeypatch, log, results, abort, rating):
    setup_sources(source, monkeypatch)
    source.prefs['livelib_username'] = ' reader '
    post = Mock(return_value=page(HEADING + book('2', str(rating))))
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    source.identify(log, results, abort, title='Книга', authors=['Автор'])
    assert results.qsize() == 3
    while not results.empty():
        mi = results.get_nowait()
        assert mi.rating == rating
        assert mi.comments.startswith('Аннотация')
        assert 'Моя оценка LiveLib: %s / 5' % format(rating, 'g').replace('.', ',') in mi.comments
        assert 'Дата прочтения LiveLib: Октябрь 2026 г.' in mi.comments
    post.assert_called_once()
    assert '/reader/reader/read/listview/biglist' in post.call_args.args[0]


@pytest.mark.parametrize('disable', ['username', 'source', 'covers'])
def test_personal_requests_are_opt_in(source, monkeypatch, log, results, abort, disable):
    setup_sources(source, monkeypatch)
    source.prefs['livelib_username'] = '' if disable == 'username' else 'reader'
    source.prefs['use_livelib'] = disable != 'source'
    post = Mock()
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    if disable == 'covers':
        source.covers.find_all_cover_urls(log, abort, 'Книга', ['Автор'], {}, 10)
    else:
        source.identify(log, results, abort, title='Книга', authors=['Автор'])
    post.assert_not_called()


@pytest.mark.parametrize('response', [OSError('private profile'), page(book('999')),
                                    page(HEADING + book('2', None))])
def test_personal_failure_or_missing_rating_keeps_public_rating(
        source, monkeypatch, log, results, abort, response):
    setup_sources(source, monkeypatch)
    original = source.litres.fetch_litres_book
    def rated(*args):
        mi = original(*args)
        mi.rating = 9
        return mi
    monkeypatch.setattr(source.litres, 'fetch_litres_book', rated)
    source.prefs['livelib_username'] = 'reader'
    post = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
    monkeypatch.setattr(source.transport, 'post_form_json', post)
    source.identify(log, results, abort, identifiers={'litres': '1'})
    mi = results.get_nowait()
    assert mi.rating == 4.5
    assert 'Моя оценка LiveLib:' not in mi.comments


def test_post_form_transport(source, monkeypatch):
    def open_request(request, timeout):
        assert request.get_method() == 'POST'
        assert request.data == b'page_no=2&per_page=100'
        headers = {k.lower(): v for k, v in request.header_items()}
        assert headers['x-requested-with'] == 'XMLHttpRequest'
        assert headers['content-type'] == 'application/x-www-form-urlencoded'
        assert 'accept-version' not in headers
        assert timeout == 7
        return SimpleNamespace(read=lambda: json.dumps(page('')).encode())
    monkeypatch.setattr(transport, 'urlopen', open_request)
    assert source.transport.post_form_json('https://www.livelib.ru/reader/test/read/listview/biglist',
                                          {'page_no': 2, 'per_page': 100}, 7) == page('')
