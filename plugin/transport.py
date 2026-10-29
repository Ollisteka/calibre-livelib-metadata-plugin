from .constants import BASE_URL
from .constants import LITRES_WEB_BASE
from .constants import USER_AGENT
from urllib.request import Request
from urllib.request import urlopen
import json


class Transport:
    """HTTP text and JSON profiles; no provider or ranking policy."""

    def fetch_url(self, url, timeout):
        headers = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': BASE_URL + '/',
        }
        raw = urlopen(Request(url, headers=headers), timeout=timeout).read()
        return raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw

    def fetch_json(self, url, timeout):
        headers = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.7',
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Version': '2',
            'Referer': LITRES_WEB_BASE + '/',
        }
        raw = urlopen(Request(url, headers=headers), timeout=timeout).read()
        return json.loads(raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw)
