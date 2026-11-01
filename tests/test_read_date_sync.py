import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('reading_sync',
    Path(__file__).resolve().parents[1] / 'reading_plugin/sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def database(existing=None, identifier='22'):
    db = Mock()
    db.field_metadata.custom_field_metadata.return_value = {
        '#read': {'datatype': 'datetime'}, '#text': {'datatype': 'text'}}
    db.all_book_ids.return_value = {1}
    db.field_for.side_effect = lambda key, book: {'livelib': identifier} if key == 'identifiers' else existing
    db.set_field.return_value = {1}
    return db


def test_empty_date_is_written_without_touching_other_fields():
    db = database()
    value = datetime(2026, 11, 1)
    assert sync.apply_dates(db, '#read', {1: value}, {1: '22'}) == {1}
    db.set_field.assert_called_once_with('#read', {1: value})


@pytest.mark.parametrize('existing', [None, datetime(101, 1, 1)])
def test_empty_date_representations(existing):
    db = database(existing)
    sync.apply_dates(db, '#read', {1: datetime(2026, 1, 1)}, {1: '22'})
    db.set_field.assert_called_once()


def test_populated_date_requires_explicit_overwrite():
    db = database(datetime(2025, 1, 1))
    args = db, '#read', {1: datetime(2026, 1, 1)}, {1: '22'}
    assert sync.apply_dates(*args) == set()
    db.set_field.assert_not_called()
    assert sync.apply_dates(*args, overwrite=True) == {1}


@pytest.mark.parametrize('overwrite', [False, True])
def test_equal_date_is_reported_as_unchanged(overwrite):
    value = datetime(2026, 1, 1)
    db = database(value)
    report = {}
    assert sync.apply_dates(db, '#read', {1: value}, {1: '22'}, overwrite, report) == set()
    assert report == {'unchanged': 1, 'preserved': 0, 'changed_book': 0}
    db.set_field.assert_not_called()


def test_changed_identity_and_deleted_book_are_skipped():
    db = database(identifier='33')
    report = {}
    assert sync.apply_dates(db, '#read', {1: datetime(2026, 1, 1), 2: datetime(2026, 1, 1)},
                            {1: '22', 2: '44'}, overwrite=True, report=report) == set()
    assert report['changed_book'] == 2
    db.set_field.assert_not_called()


def test_missing_date_never_clears_existing_value():
    db = database(datetime(2025, 1, 1))
    assert sync.apply_dates(db, '#read', {1: None}, {1: '22'}, overwrite=True) == set()
    db.set_field.assert_not_called()


@pytest.mark.parametrize('column', ['#text', '#deleted', 'pubdate'])
def test_invalid_destination_rejected(column):
    db = database()
    with pytest.raises(ValueError):
        sync.apply_dates(db, column, {1: datetime(2026, 1, 1)}, {1: '22'})
    db.set_field.assert_not_called()
