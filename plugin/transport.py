from .constants import FANTLAB_BASE_URL
from .constants import BASE_URL
from .constants import LITRES_WEB_BASE
from .constants import USER_AGENT
from urllib.request import Request
from urllib.request import urlopen
from urllib.parse import urlencode
import json


class Transport:
    """HTTP text and JSON profiles; no provider or ranking policy."""

    def post_form_json(self, url, fields, timeout):
        headers = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': BASE_URL + '/',
        }
        request = Request(url, data=urlencode(fields).encode('utf-8'), headers=headers)
        raw = urlopen(request, timeout=timeout).read()
        return json.loads(raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw)

    def _read(self, url, timeout, headers):
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            raw = response.read()
        return raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw

    def fetch_fantlab_json(self, url, timeout):
        return json.loads(self._read(url, timeout, {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'application/json,text/plain,*/*',
            'Referer': FANTLAB_BASE_URL + '/',
        }))

    def fetch_livelib_text(self, url, timeout):
        headers = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': BASE_URL + '/',
        }
        return self._read(url, timeout, headers)

    def fetch_litres_json(self, url, timeout):
        headers = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Version': '2',
            'Referer': LITRES_WEB_BASE + '/',
        }
        return json.loads(self._read(url, timeout, headers))
