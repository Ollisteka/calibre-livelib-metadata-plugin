from datetime import datetime

import pytest

from plugin_under_test.providers.livelib.dates import parse_read_date


@pytest.mark.parametrize('text, expected', [
    ('Ноябрь 2026 г.', datetime(2026, 11, 1)),
    ('2026', datetime(2026, 1, 1)),
    ('2026 год', datetime(2026, 1, 1)),
    ('  Октябрь\u00a02026 г. ', datetime(2026, 10, 1)),
    ('29 февраля 2024 года', datetime(2024, 2, 29)),
    ('15.11.2026', datetime(2026, 11, 15)),
    ('2026-11-15', datetime(2026, 11, 15)),
])
def test_calendar_date(text, expected):
    assert parse_read_date(text) == expected


@pytest.mark.parametrize('text', [None, '', 'Не помню', 'Сегодня', '2026-11',
    '29 февраля 2025', '31.04.2026', '13.13.2026', '0000',
    'Ноябрь 2026 — декабрь 2026', 'Ноябрь', 'Середина 2026'])
def test_invalid_dates_are_not_invented(text):
    assert parse_read_date(text) is None
