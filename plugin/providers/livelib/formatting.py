from html import escape


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
    block = '<p><b>Детали издания LiveLib:</b><br/>%s</p>' % '<br/>'.join(escape(row) for row in rows)
    return ((comments or '') + block) if comments else block
