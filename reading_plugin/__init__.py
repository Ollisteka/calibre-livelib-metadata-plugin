from calibre.customize import InterfaceActionBase


class LiveLibReadingDates(InterfaceActionBase):
    name = 'LiveLib Reading Dates'
    description = 'Сохранение даты прочтения LiveLib в пользовательскую колонку'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'OpenAI Codex for Emin'
    version = (0, 1, 0)
    minimum_calibre_version = (6, 0, 0)
    actual_plugin = 'calibre_plugins.livelib_reading_dates.ui:ReadingDatesAction'
