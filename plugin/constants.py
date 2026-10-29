import re


BASE_URL = 'https://www.livelib.ru'
BETA_BASE_URL = 'https://beta.livelib.ru'
FANTLAB_BASE_URL = 'https://fantlab.ru'
FANTLAB_API_BASE_URL = 'https://api.fantlab.ru'
LITRES_API_BASE = 'https://api.litres.ru/foundation/api'
LITRES_WEB_BASE = 'https://www.litres.ru'
IDENTIFIER_TYPE_LITRES = 'litres'
IDENTIFIER_TYPE_LIVELIB = 'livelib'
IDENTIFIER_TYPE_FANTLAB = 'fantlab'
IDENTIFIER_TYPE_ISBN = 'isbn'
FANTLAB_IDENTIFIER_PATTERN = re.compile(r'[a-z][a-z0-9_-]*\d+', re.IGNORECASE)
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/126.0.0.0 Safari/537.36'
)
