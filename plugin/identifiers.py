from .constants import BASE_URL
from .constants import BETA_BASE_URL
from .constants import FANTLAB_BASE_URL
from .constants import FANTLAB_IDENTIFIER_PATTERN
from .constants import IDENTIFIER_TYPE_FANTLAB
from .constants import IDENTIFIER_TYPE_LITRES
from .constants import IDENTIFIER_TYPE_LIVELIB
from .constants import LITRES_WEB_BASE
from calibre import as_unicode
from urllib.parse import urlsplit
import re


def livelib_id_from_url(url):
    return (url or '').split('/book/', 1)[-1].split('?', 1)[0].split('#', 1)[0]


def fantlab_identifier_from_url(url):
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.netloc.lower() not in ('api.fantlab.ru', 'fantlab.ru'):
        return None
    path = parsed.path.strip('/')
    return path if FANTLAB_IDENTIFIER_PATTERN.fullmatch(path) else None


def livelib_beta_url(url):
    livelib_id = livelib_id_from_url(url)
    return BETA_BASE_URL + '/book/' + livelib_id if livelib_id else url


def get_book_url(identifiers):
    urls = get_book_urls(identifiers)
    return urls[0] if urls else None


def get_book_urls(identifiers):
    urls = []
    for kind, base, pattern in (
            (IDENTIFIER_TYPE_LITRES, LITRES_WEB_BASE + '/book/', r'\d+'),
            (IDENTIFIER_TYPE_LIVELIB, BASE_URL + '/book/', r'\d+(?:-[\w-]+)?'),
            (IDENTIFIER_TYPE_FANTLAB, FANTLAB_BASE_URL + '/', FANTLAB_IDENTIFIER_PATTERN)):
        value = as_unicode((identifiers or {}).get(kind) or '')
        if value and re.fullmatch(pattern, value):
            urls.append((kind, value, base + value))
    return urls


def id_from_url(url):
    try:
        parsed = urlsplit(url or '')
        host = (parsed.hostname or '').lower()
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https'):
        return None
    if host in ('livelib.ru', 'www.livelib.ru', 'beta.livelib.ru'):
        match = re.fullmatch(r'/book/(\d+(?:-[\w-]+)?)/?', parsed.path)
        if match:
            return (IDENTIFIER_TYPE_LIVELIB, match.group(1))
    if host in ('litres.ru', 'www.litres.ru'):
        match = re.fullmatch(r'/(?:book|audiobook)/(?:(?:[^/]+/)?[^/]*-)?(\d+)/?', parsed.path)
        if match:
            return (IDENTIFIER_TYPE_LITRES, match.group(1))
    if host in ('fantlab.ru', 'www.fantlab.ru', 'api.fantlab.ru'):
        value = parsed.path.strip('/')
        if FANTLAB_IDENTIFIER_PATTERN.fullmatch(value):
            return (IDENTIFIER_TYPE_FANTLAB, value)
    return None


def get_book_url_name(idtype, default_name):
    names = {
        IDENTIFIER_TYPE_LITRES: 'LitRes',
        IDENTIFIER_TYPE_LIVELIB: 'LiveLib',
        IDENTIFIER_TYPE_FANTLAB: 'FantLab',
    }
    return names.get(idtype, default_name)
