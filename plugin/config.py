"""Options rendered and persisted by Calibre's metadata Source."""
from calibre.ebooks.metadata.sources.base import Option


SOURCE_NAMES = ('litres', 'livelib', 'fantlab')
SOURCE_OPTIONS = tuple(
    Option('use_' + key, 'bool', True, 'Использовать ' + label,
           'Получать метаданные и обложки из ' + label +
           '. Отключение не удаляет сохранённые идентификаторы.')
    for key, label in zip(SOURCE_NAMES, ('LitRes', 'LiveLib', 'FantLab'))
)
PERSONAL_OPTIONS = (
    Option('livelib_username', 'string', '', 'Имя пользователя LiveLib',
           'Логин из адреса livelib.ru/reader/логин. Используется, чтобы загрузить личную оценку '
           'и дату прочтения из публичного списка «Прочитал». Оценка подставляется в одноимённое '
           'поле calibre; поведение без личной оценки задаётся ниже. '
           'Оценка и дата также добавляются в детали LiveLib. '
           'Оставьте пустым, чтобы отключить.'),
    Option('livelib_rating_fallback', 'choices', 'none',
           'Если личная оценка LiveLib не найдена',
           'При указанном имени пользователя: использовать общую оценку книги '
           'из метаданных включённых источников или не переносить оценку. '
           'Применяется также, если профиль недоступен или время поиска истекло. '
           'Найденная личная оценка всегда имеет приоритет.',
           choices={'public': 'Использовать общую оценку книги',
                    'none': 'Не переносить оценку'}),
)


def enabled_sources(prefs):
    return frozenset(key for key in SOURCE_NAMES if prefs['use_' + key])
