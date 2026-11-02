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
    litres_id = identifiers.get(IDENTIFIER_TYPE_LITRES)
    if litres_id:
        return (IDENTIFIER_TYPE_LITRES, litres_id, LITRES_WEB_BASE + '/book/' + litres_id)
    livelib_id = identifiers.get(IDENTIFIER_TYPE_LIVELIB)
    if livelib_id:
        return (IDENTIFIER_TYPE_LIVELIB, livelib_id, BASE_URL + '/book/' + livelib_id)
    fantlab_id = identifiers.get(IDENTIFIER_TYPE_FANTLAB)
    if fantlab_id and FANTLAB_IDENTIFIER_PATTERN.fullmatch(as_unicode(fantlab_id)):
        return (IDENTIFIER_TYPE_FANTLAB, fantlab_id, FANTLAB_BASE_URL + '/' + as_unicode(fantlab_id))


def id_from_url(url):
    match = re.search(r'livelib\.ru/book/([^/?#]+)', url or '')
    if match:
        return (IDENTIFIER_TYPE_LIVELIB, match.group(1))
    return None


def get_book_url_name(idtype, default_name):
    names = {
        IDENTIFIER_TYPE_LITRES: 'Litres',
        IDENTIFIER_TYPE_LIVELIB: 'LiveLib',
        IDENTIFIER_TYPE_FANTLAB: 'FantLab',
    }
    return names.get(idtype, default_name)
