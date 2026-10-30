"""Options rendered and persisted by Calibre's metadata Source."""
from calibre.ebooks.metadata.sources.base import Option


SOURCE_NAMES = ('litres', 'livelib', 'fantlab')
SOURCE_OPTIONS = tuple(
    Option('use_' + key, 'bool', True, 'Использовать ' + label,
           'Получать метаданные и обложки из ' + label +
           '. Отключение не удаляет сохранённые идентификаторы.')
    for key, label in zip(SOURCE_NAMES, ('LitRes', 'LiveLib', 'FantLab'))
)


def enabled_sources(prefs):
    return frozenset(key for key in SOURCE_NAMES if prefs['use_' + key])
