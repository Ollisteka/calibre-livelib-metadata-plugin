"""Public read shelf, using the biglist endpoint documented by livelib-backup.

Only exact numeric edition IDs match. Dates remain human-readable: LiveLib can
group books by month/year without specifying a day. No title-based guessing.
"""
from time import monotonic
from urllib.parse import quote
import math
import re

from ...constants import BASE_URL
from ...html_utils import safe_html_fromstring
from .formatting import append_personal_details


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

    def __init__(self, transport):
        self.transport = transport
        self._username = None
        self._expires = 0
        self._entries = {}
        self._next_page = 1
        self._date = None
        self._complete = False
        self._seen_pages = set()

    def lookup(self, username, identifiers, log, abort, timeout):
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
        deadline = monotonic() + timeout
        url = BASE_URL + '/reader/' + quote(username, safe='') + '/read/listview/biglist'
        while not self._complete and not wanted.issubset(self._entries):
            remaining = deadline - monotonic()
            if abort.is_set() or remaining <= 0:
                break
            try:
                response = self.transport.post_form_json(url, {
                    'page_no': self._next_page, 'per_page': 100,
                    'is_new_design': 'll2015b', 'is_prev': 'false',
                }, remaining)
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
            except Exception:
                log.exception('LiveLib personal data unavailable; keeping public metadata')
                break
        if abort.is_set():
            return {}
        missing = wanted - self._entries.keys()
        if missing:
            log.info('LiveLib personal data: %d edition(s) %s' %
                     (len(missing), 'not on read shelf' if self._complete else 'not reached (scan incomplete)'))
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
