"""Public read shelf with precise dates and a legacy biglist fallback.

Only exact numeric edition IDs match. Dates remain human-readable: LiveLib can
omit calendar components. No title-based guessing.
"""
from time import monotonic
from urllib.parse import quote
import math
import re
import json

from ...constants import BASE_URL
from ...html_utils import safe_html_fromstring
from .formatting import append_personal_details
from .dates import MONTHS, parse_read_date
from .parsers import decode_next_payload


def precise_date(value):
    """Format only the calendar components actually supplied by the read shelf."""
    if not isinstance(value, dict):
        return None
    year, month, day = (value.get(key) for key in ('year', 'month', 'day'))
    if type(year) is not int or not 1 <= year <= 9999:
        return None
    if month is None and day is None:
        return '%d г.' % year
    if type(month) is not int or not 1 <= month <= 12:
        return None
    if day is None:
        name = next(name for name, number in MONTHS.items() if number == month)
        return '%s %d г.' % (name.capitalize(), year)
    if type(day) is not int:
        return None
    result = '%02d.%02d.%04d' % (day, month, year)
    return result if parse_read_date(result) is not None else None


def parse_public_read_page(content, page_number):
    """Read the public Next.js shelf query, never dates from other page objects."""
    payload = decode_next_payload(content)
    for match in re.finditer(r'"queries"\s*:\s*\[', payload):
        try:
            queries, _ = json.JSONDecoder().raw_decode(payload, match.end() - 1)
        except ValueError:
            continue
        for query in queries:
            if not isinstance(query, dict):
                continue
            key = query.get('queryKey')
            if (not isinstance(key, list) or len(key) != 6
                    or key[0:2] != ['users', 'detail']
                    or key[3:5] != ['profile', 'reads']):
                continue
            params = key[5]
            if (not isinstance(params, dict) or params.get('ordering') != 'read_at_desc'
                    or params.get('offset') != (page_number - 1) * params.get('limit', 0)):
                continue
            response = query.get('state', {}).get('data')
            if not isinstance(response, dict) or response.get('status') != 200:
                continue
            data = response.get('payload', {})
            rows, pagination = data.get('data'), data.get('pagination')
            if not isinstance(rows, list) or not isinstance(pagination, dict) or 'next_page' not in pagination:
                continue
            entries = {}
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('art_edition'), dict):
                    continue
                identifier = edition_id(row['art_edition'].get('id'))
                if identifier is None:
                    continue
                entry = {}
                date = precise_date(row.get('read_date'))
                if date:
                    entry['read_date'] = date
                # This endpoint uses 0..10 for the owner's rating, not 0..5.
                rating = row.get('rating')
                if type(rating) in (int, float) and math.isfinite(rating) and 0 < rating <= 10:
                    entry['rating'] = rating / 2
                entries.setdefault(identifier, entry)
            return entries, pagination['next_page'] is None
    raise ValueError('Public LiveLib read shelf data not found')


def has_class(name):
    return "contains(concat(' ', normalize-space(@class), ' '), ' %s ')" % name


def edition_id(value):
    match = re.fullmatch(r'(\d+)(?:-[\w-]+)?', str(value or ''))
    return match.group(1) if match else None


def parse_read_page(content, current_date=None):
    """Return entries and the heading to carry over to the next page."""
    root = safe_html_fromstring('<div>' + content + '</div>')
    entries = {}
    nodes = root.xpath('//*[%s or %s]' % (has_class('brow-h2'), has_class('book-item-manage')))
    for node in nodes:
        if 'brow-h2' in node.get('class', '').split():
            current_date = ' '.join(' '.join(node.xpath('.//h2//text()')).split()) or None
            continue
        hrefs = node.xpath('.//a[%s]/@href' % has_class('brow-book-name'))
        match = re.search(r'/book/(\d+)(?:-|/|$|[?#])', hrefs[0]) if hrefs else None
        if not match:
            continue
        entry = {}
        if current_date:
            entry['read_date'] = current_date
        # The overall rating is in brow-cover; only brow-ratings belongs to
        # the shelf owner. Missing personal ratings must never borrow it.
        ratings = node.xpath('.//*[%s]//span[%s]' %
                             (has_class('brow-ratings'), has_class('rating-value')))
        if ratings:
            try:
                rating = float(ratings[0].text_content().strip().replace(',', '.'))
                if math.isfinite(rating) and 0 < rating <= 5:
                    entry['rating'] = rating
            except ValueError:
                pass
        # Re-reads can produce more than one row; the shelf lists newest first.
        entries.setdefault(match.group(1), entry)
    return entries, current_date


class ReadingHistory:
    """Short-lived, per-plugin cache. Incomplete scans resume on the next lookup."""

    CACHE_SECONDS = 300
    REQUEST_SECONDS = 10

    def __init__(self, transport):
        self.status = "incomplete"
        self.reason = ""
        self.transport = transport
        self._username = None
        self._expires = 0
        self._entries = {}
        self._next_page = 1
        self._date = None
        self._complete = False
        self._seen_pages = set()
        self._backend = None

    def lookup(self, username, identifiers, log, abort, timeout):
        self.status, self.reason = "incomplete", "Обход не завершён"
        username = username.strip()
        wanted = {edition_id(value) for value in identifiers} - {None}
        if not username or not wanted or timeout <= 0 or abort.is_set():
            return {}
        if username != self._username or monotonic() >= self._expires:
            self._username = username
            self._expires = monotonic() + self.CACHE_SECONDS
            self._entries = {}
            self._next_page = 1
            self._date = None
            self._complete = False
            self._seen_pages = set()
            self._backend = None
        deadline = monotonic() + timeout
        url = BASE_URL + '/reader/' + quote(username, safe='') + '/read/listview/biglist'
        while not self._complete and not wanted.issubset(self._entries):
            remaining = deadline - monotonic()
            if abort.is_set() or remaining <= 0:
                break
            try:
                if self._backend is None:
                    try:
                        content = self.transport.fetch_livelib_text(
                            BASE_URL + '/reader/' + quote(username, safe='') + '/read?ordering=read_at_desc&page=1',
                            min(remaining / 2, self.REQUEST_SECONDS))
                        entries, complete = parse_public_read_page(content, 1)
                        self._backend = 'public'
                    except Exception:
                        self._backend = 'legacy'
                        log.info('LiveLib exact dates unavailable; using month/year shelf headings')
                    if abort.is_set():
                        return {}
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                elif self._backend == 'public':
                    content = self.transport.fetch_livelib_text(
                        BASE_URL + '/reader/' + quote(username, safe='')
                        + '/read?ordering=read_at_desc&page=%d' % self._next_page,
                        min(remaining, self.REQUEST_SECONDS))
                    entries, complete = parse_public_read_page(content, self._next_page)
                if self._backend == 'public':
                    signature = frozenset(entries)
                    if not complete and (not entries or signature in self._seen_pages):
                        raise ValueError('LiveLib read shelf pagination did not advance')
                    self._seen_pages.add(signature)
                    for identifier, entry in entries.items():
                        self._entries.setdefault(identifier, entry)
                    self._next_page += 1
                    self._complete = complete
                    continue
                response = self.transport.post_form_json(url, {
                    'page_no': self._next_page, 'per_page': 100,
                    'is_new_design': 'll2015b', 'is_prev': 'false',
                }, min(remaining, self.REQUEST_SECONDS))
                if (not isinstance(response, dict) or response.get('error_code', 0) != 0
                        or not isinstance(response.get('content'), str)
                        or not isinstance(response.get('last_page'), bool)):
                    raise ValueError('Unexpected or inaccessible LiveLib read shelf')
                content = response['content']
                entries, next_date = parse_read_page(content, self._date)
                signature = frozenset(entries)
                if not response['last_page'] and (not entries or signature in self._seen_pages):
                    raise ValueError('LiveLib read shelf pagination did not advance')
                self._seen_pages.add(signature)
                for identifier, entry in entries.items():
                    self._entries.setdefault(identifier, entry)
                self._date = next_date
                self._next_page += 1
                self._complete = response['last_page']
            except Exception as err:
                self.status, self.reason = "error", str(err)
                log.exception('LiveLib personal data unavailable; keeping public metadata')
                break
        if abort.is_set():
            return {}
        if self.status != "error":
            self.status = "complete" if self._complete or wanted.issubset(self._entries) else "incomplete"
            self.reason = "" if self.status == "complete" else "Истёк бюджет обхода"
        missing = wanted - self._entries.keys()
        if missing:
            log.info('LiveLib personal data: %d edition(s) %s' %
                     (len(missing), 'not on read shelf' if self._complete else 'not reached (scan incomplete)'))
        for identifier in sorted(wanted & self._entries.keys()):
            log.info('LiveLib read date: %s = %s (%s)' % (
                identifier, self._entries[identifier].get('read_date', 'not specified'), self._backend))
        return {identifier: self._entries[identifier] for identifier in wanted if identifier in self._entries}

    def enrich(self, results, username, log, abort, timeout):
        entries = self.lookup(username, [mi.identifiers.get('livelib') for mi in results],
                              log, abort, timeout)
        for mi in results:
            entry = entries.get(edition_id(mi.identifiers.get('livelib')))
            if not entry:
                continue
            if 'rating' in entry:
                mi.rating = entry['rating'] * 2  # Calibre stores 0..10.
            mi.comments = append_personal_details(mi.comments, entry)
