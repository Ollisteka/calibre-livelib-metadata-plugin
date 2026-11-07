"""Public shelf fixtures retain the field structure observed on LiveLib."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugin_under_test.providers.livelib.reading import (
    ReadingHistory, parse_public_read_page, precise_date,
)
from plugin_under_test.providers.livelib.dates import parse_read_date


def shelf(rows, page=1, last=True):
    query = {
        'queryKey': ['users', 'detail', 123, 'profile', 'reads', {
            'limit': 20, 'offset': (page - 1) * 20, 'ordering': 'read_at_desc'}],
        'state': {'data': {'status': 200, 'payload': {
            'data': rows, 'pagination': {'next_page': None if last else '/api/next'}}}},
    }
    payload = '6:' + json.dumps(['$', 'Component', None, {'state': {'queries': [query]}}])
    return '<script>self.__next_f.push(%s)</script>' % json.dumps([1, payload])


def row(identifier=1018349278, date=None, rating=10):
    return {'id': 53353186, 'art_edition': {'id': identifier,
            'publication_year': 2026, 'stats': {'rating': '7.200'}},
            'rating': rating, 'status_set_at': '2026-11-03T11:30:08',
            'read_date': date if date is not None else {'year': 2026, 'month': 11, 'day': 2}}


def history(*pages):
    transport = SimpleNamespace(fetch_livelib_text=Mock(side_effect=pages), post_form_json=Mock())
    return ReadingHistory(transport)


def test_exact_day_comes_from_read_date_not_status_set_at_or_publication_year():
    entries, last = parse_public_read_page(shelf([row()]), 1)
    assert last
    assert entries == {'1018349278': {'read_date': '02.11.2026', 'rating': 5}}
    assert parse_read_date(entries['1018349278']['read_date']).day == 2


@pytest.mark.parametrize('value, expected', [
    ({'year': 2026, 'month': 11, 'day': None}, 'Ноябрь 2026 г.'),
    ({'year': 2025, 'month': None, 'day': None}, '2025 г.'),
    ({'year': 2024, 'month': 2, 'day': 29}, '29.02.2024'),
    ({'year': 2025, 'month': 2, 'day': 29}, None),
    ({'year': 2026, 'month': None, 'day': 2}, None),
    ({'year': True}, None), ({'year': 2026, 'month': 13}, None),
    ({'year': '2026'}, None), (None, None),
])
def test_calendar_precision_and_invalid_dates(value, expected):
    assert precise_date(value) == expected


def test_absent_personal_date_and_rating_never_use_other_fields():
    item = row()
    item['read_date'] = None
    item['rating'] = None
    assert parse_public_read_page(shelf([item]), 1)[0] == {'1018349278': {}}


def test_pagination_cache_rereads_and_username_change(log, abort):
    first = shelf([row()], last=False)
    second = shelf([row(rating=4), row(22, rating=9)], page=2)
    h = history(first, second, shelf([row(rating=8)]))
    found = h.lookup('reader', ['1018349278', '22'], log, abort, 30)
    assert found['1018349278']['rating'] == 5
    assert found['22']['rating'] == 4.5
    assert h.status == 'complete'
    assert 'page=2' in h.transport.fetch_livelib_text.call_args.args[0]
    assert h.lookup('reader', ['22'], log, abort, 30) == {'22': found['22']}
    assert h.transport.fetch_livelib_text.call_count == 2
    assert h.lookup('other_reader', ['1018349278'], log, abort, 30)['1018349278']['rating'] == 4
    h.transport.post_form_json.assert_not_called()


def test_partial_scan_error_keeps_exact_dates_and_resumes(log, abort):
    h = history(shelf([row()], last=False), OSError('offline'), shelf([row(22)], page=2))
    assert '1018349278' in h.lookup('reader', ['1018349278', '22'], log, abort, 30)
    assert h.status == 'error'
    assert h.lookup('reader', ['22'], log, abort, 30)['22']['read_date'] == '02.11.2026'
    assert h.status == 'complete'
    assert h.transport.fetch_livelib_text.call_args_list[1].args[0] == h.transport.fetch_livelib_text.call_args_list[2].args[0]


def test_repeated_page_does_not_loop_or_fall_back_to_month(log, abort):
    h = history(shelf([row()], last=False), shelf([row()], page=2, last=False))
    found = h.lookup('reader', ['22', '1018349278'], log, abort, 30)
    assert found['1018349278']['read_date'] == '02.11.2026'
    assert h.status == 'error'
    assert h.transport.fetch_livelib_text.call_count == 2
    h.transport.post_form_json.assert_not_called()


def test_cancel_after_public_request_discards_dates(log, abort):
    h = history()
    def fetch(*args):
        abort.set()
        return shelf([row()])
    h.transport.fetch_livelib_text.side_effect = fetch
    assert h.lookup('reader', ['1018349278'], log, abort, 30) == {}
    h.transport.post_form_json.assert_not_called()


def test_deadline_after_failed_probe_prevents_fallback_request(monkeypatch, log, abort):
    from plugin_under_test.providers.livelib import reading
    clock = [0]
    monkeypatch.setattr(reading, 'monotonic', lambda: clock[0])
    h = history()
    def fetch(*args):
        clock[0] = 31
        raise OSError('timeout')
    h.transport.fetch_livelib_text.side_effect = fetch
    assert h.lookup('reader', ['22'], log, abort, 30) == {}
    h.transport.post_form_json.assert_not_called()


def test_other_collection_or_wrong_page_is_not_used():
    wrong_collection = shelf([row()]).replace('reads', 'wants')
    for content in (wrong_collection, shelf([row()], page=2), '<html>Login</html>'):
        with pytest.raises(ValueError):
            parse_public_read_page(content, 1)
