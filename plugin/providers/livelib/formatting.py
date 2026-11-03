from html import escape


DETAILS_START = '<p><b>Детали издания LiveLib:</b><br/>'


def append_personal_details(comments, entry):
    rows = []
    if entry.get('rating') is not None:
        rows.append('Моя оценка LiveLib: %s / 5' % format(entry['rating'], 'g').replace('.', ','))
    if entry.get('read_date'):
        rows.append('Дата прочтения LiveLib: %s' % entry['read_date'])
    if not rows:
        return comments
    extra = '<br/>'.join(escape(row) for row in rows)
    # The provider-generated edition block is the final paragraph. Extend it
    # without reserializing the original annotation or adding a second heading.
    if (comments and DETAILS_START in comments and comments.endswith('</p>')
            and '</p>' not in comments.rsplit(DETAILS_START, 1)[1][:-4]):
        return comments[:-4] + '<br/>' + extra + '</p>'
    return (comments or '') + DETAILS_START + extra + '</p>'


def append_edition_details(comments, details, rating_count=None):
    rows = []
    labels = [
        ('isbn', 'ISBN'),
        ('publisher', 'Издательство'),
        ('series', 'Серия'),
        ('year', 'Год издания'),
        ('language', 'Язык'),
        ('physical', 'Формат'),
        ('pages', 'Страниц'),
        ('cover_type', 'Тип обложки'),
        ('paper_type', 'Тип бумаги'),
        ('weight', 'Вес'),
        ('size', 'Размер'),
        ('age', 'Возрастные ограничения'),
    ]
    for key, label in labels:
        value = details.get(key)
        if value:
            rows.append('%s: %s' % (label, value))
    if rating_count:
        rows.append('Оценок LiveLib: %s' % rating_count)
    if not rows:
        return comments
    block = DETAILS_START + '<br/>'.join(escape(row) for row in rows) + '</p>'
    return ((comments or '') + block) if comments else block
