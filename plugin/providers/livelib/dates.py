"""Convert shelf headings without guessing unsupported or ambiguous dates."""
from datetime import datetime
import re


MONTHS = {
    name: month
    for month, names in enumerate((
        ('январь', 'января'), ('февраль', 'февраля'), ('март', 'марта'),
        ('апрель', 'апреля'), ('май', 'мая'), ('июнь', 'июня'),
        ('июль', 'июля'), ('август', 'августа'), ('сентябрь', 'сентября'),
        ('октябрь', 'октября'), ('ноябрь', 'ноября'), ('декабрь', 'декабря'),
    ), 1)
    for name in names
}


def parse_read_date(value):
    """Return a naive calendar datetime, or None; missing month/day become 1.

    The caller must localize it using calibre's local timezone before storage.
    Keep the original shelf heading in comments to retain its actual precision.
    """
    if not isinstance(value, str):
        return None
    value = ' '.join(value.lower().split())
    value = re.sub(r'\s*(?:г\.?|года|год)$', '', value).strip()
    year = month = day = None
    if re.fullmatch(r'\d{4}', value):
        year, month, day = int(value), 1, 1
    else:
        match = re.fullmatch(r'(?:(\d{1,2})\s+)?([а-я]+)\s+(\d{4})', value)
        if match:
            day, month, year = int(match[1] or 1), MONTHS.get(match[2]), int(match[3])
        else:
            match = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', value)
            if match:
                day, month, year = map(int, match.groups())
            else:
                match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', value)
                if match:
                    year, month, day = map(int, match.groups())
    if None in (year, month, day):
        return None
    try:
        return datetime(year, month, day)
    except ValueError:
        return None
