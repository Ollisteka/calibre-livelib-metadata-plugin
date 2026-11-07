"""Library-specific settings and conservative date updates (no GUI/network)."""
PREF_KEY = 'livelib_reading_dates'


def date_columns(db):
    return {key: meta for key, meta in db.field_metadata.custom_field_metadata().items()
            if meta['datatype'] == 'datetime'}


def apply_dates(db, column, values, identifiers, overwrite=False, report=None):
    """Recheck identities and current values after the network request."""
    if column not in date_columns(db):
        raise ValueError('Выбранная колонка даты удалена или изменила тип.')
    changes = {}
    if report is None:
        report = {}
    report.update(unchanged=0, preserved=0, changed_book=0)
    existing_ids = db.all_book_ids()
    for book_id, value in values.items():
        if value is None:
            continue
        if book_id not in existing_ids:
            report["changed_book"] += 1
            continue
        if db.field_for('identifiers', book_id).get('livelib') != identifiers[book_id]:
            report['changed_book'] += 1
            continue
        current = db.field_for(column, book_id)
        # Calibre can represent an empty date with its year-101 sentinel.
        empty = current is None or current.year <= 101
        if current == value:
            report['unchanged'] += 1
        elif overwrite or empty:
            changes[book_id] = value
        else:
            report['preserved'] += 1
    return db.set_field(column, changes) if changes else set()
