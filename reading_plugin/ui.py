from threading import Event
from io import StringIO

from qt.core import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QIcon, QLabel,
                     QPixmap, QProgressDialog, QThread, QVBoxLayout, Qt, QApplication)
from calibre.customize.ui import metadata_plugins
from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.utils.date import local_tz
from calibre.ebooks.metadata.sources.base import create_log

from .dates import parse_read_date
from .sync import PREF_KEY, apply_dates, date_columns


IDENTIFIER_HELP = (
    'Книги без идентификатора livelib пропускаются. Чтобы добавить его, запустите '
    'загрузку метаданных с включённым источником LiveLib Metadata или введите его самостоятельно:'
    '<ul>'
    '<li>откройте редактор метаданных книги;</li>'
    '<li>в поле «Идентификаторы» добавьте <code>livelib:</code>;</li>'
    '<li>сразу после двоеточия укажите часть адреса книги на LiveLib после <code>/book/</code> '
    'и до знака <code>?</code> или <code>#</code>, если они есть.</li>'
    '</ul>'
    'Например, для адреса <code>https://www.livelib.ru/book/123456789-nazvanie-knigi</code> '
    'укажите <code>livelib:123456789-nazvanie-knigi</code>. Можно указать только число: '
    '<code>livelib:123456789</code>.'
)


class SettingsDialog(QDialog):
    def __init__(self, parent, db, count):
        super().__init__(parent)
        self.setWindowTitle('Дата прочтения LiveLib')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Выделено книг: %d. Дата прочтения → колонка calibre:' % count))
        self.column = QComboBox(self)
        self.column.addItem('Выберите колонку типа «Дата»', '')
        for key, meta in sorted(date_columns(db).items()):
            self.column.addItem('%s (%s)' % (meta['name'], key), key)
        prefs = db.pref(PREF_KEY, {})
        index = self.column.findData(prefs.get('read_date_column', ''))
        self.column.setCurrentIndex(max(0, index))
        layout.addWidget(self.column)
        label = QLabel('Если конкретный день не указан — используется первое число месяца.<br>'
                       'Если не указан месяц — используется  1 января.<br>'
                       'Если книга прочитана несколько раз, сохраняется дата последнего прочтения.<br>'
                       '<br>' + 'Колонку можно создать в «Параметры» → «Добавить свои столбцы».<br>'
                       '<br>' + IDENTIFIER_HELP)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse |
                                      Qt.TextInteractionFlag.TextSelectableByMouse |
                                      Qt.TextInteractionFlag.TextSelectableByKeyboard)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.overwrite = QCheckBox('Обновлять уже заполненные даты', self)
        self.overwrite.setChecked(bool(prefs.get('overwrite', False)))
        layout.addWidget(self.overwrite)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Загрузить даты')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(520, self.sizeHint().height())

    def accept(self):
        if not self.column.currentData():
            error_dialog(self, 'Выберите колонку', 'Нужна пользовательская колонка типа «Дата».', show=True)
            return
        super().accept()


class FetchDates(QThread):
    def __init__(self, parent, source, username, identifiers, history=None):
        super().__init__(parent)
        # A private cache/transport avoids sharing mutable state with downloads.
        self.history = history if history is not None else source.create_reading_history()
        self.username, self.identifiers = username, identifiers
        self.abort = Event()
        self.log_output = StringIO()
        self.log = create_log(self.log_output)
        self.values = {}
        self.skipped = dict(absent=0, invalid=0, incomplete=0)
        self.failure = None
        self.lookup_status = "incomplete"
        self.lookup_reason = ""

    def run(self):
        try:
            from calibre_plugins.livelib_metadata.providers.livelib.reading import edition_id
            entries = self.history.lookup(self.username, self.identifiers.values(),
                                          self.log, self.abort, 120)
            self.lookup_status = self.history.status
            self.lookup_reason = self.history.reason
            for book_id, identifier in self.identifiers.items():
                key = edition_id(identifier)
                raw = entries.get(key, {}).get('read_date')
                value = parse_read_date(raw)
                if value is None:
                    reason = ('incomplete' if key not in entries and self.lookup_status != 'complete'
                              else 'invalid' if raw else 'absent')
                    self.skipped[reason] += 1
                if value is not None:
                    self.values[book_id] = value.replace(tzinfo=local_tz)
        except Exception as err:
            self.failure = str(err)


class ReadingDatesAction(InterfaceAction):
    name = 'LiveLib Reading Dates'
    action_spec = ('Загрузить даты прочтения LiveLib', None,
                   'Сохранить даты для выделенных книг', None)
    action_type = 'current'
    dont_add_to = frozenset(['context-menu-device'])

    def genesis(self):
        self.closing = False
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.worker = None
        self.history = None
        icon_path = 'images/reading-dates.png'
        pixmap = QPixmap()
        pixmap.loadFromData(self.load_resources([icon_path])[icon_path])
        self.qaction.setIcon(QIcon(pixmap))
        self.qaction.setIconText('Загрузить даты\nпрочтения LiveLib')
        self.qaction.triggered.connect(self.start)

    def start(self):
        if self.worker is not None:
            info_dialog(self.gui, "Загрузка выполняется",
                        "Дождитесь завершения запроса или отмены (таймаут запроса 10 секунд).", show=True)
            return
        if self.gui.current_view() is not self.gui.library_view:
            return
        selected = self.gui.library_view.get_selected_ids()
        if not selected:
            info_dialog(self.gui, 'Выберите книги', 'Выделите книги в библиотеке.', show=True)
            return
        source = next((p for p in metadata_plugins(['identify']) if p.name == 'LiveLib Metadata'), None)
        if source is None or not callable(getattr(source, 'create_reading_history', None)):
            error_dialog(self.gui, 'Нужен LiveLib Metadata',
                         'Установите и включите LiveLib Metadata версии 0.5.0 или новее.', show=True)
            return
        username = (source.prefs['livelib_username'] or '').strip()
        if not username or not source.prefs['use_livelib']:
            error_dialog(self.gui, 'Настройте LiveLib',
                         'В настройках источника LiveLib Metadata включите LiveLib и укажите имя пользователя.', show=True)
            return
        db = self.gui.current_db.new_api
        dialog = SettingsDialog(self.gui, db, len(selected))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        column, overwrite = dialog.column.currentData(), dialog.overwrite.isChecked()
        db.set_pref(PREF_KEY, {'read_date_column': column, 'overwrite': overwrite})
        identifiers = {i: db.field_for('identifiers', i).get('livelib') for i in selected}
        identifiers = {i: value for i, value in identifiers.items() if value}
        if not identifiers:
            message = info_dialog(self.gui, 'Нет идентификаторов LiveLib', IDENTIFIER_HELP)
            for label in message.findChildren(QLabel):
                label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse |
                                              Qt.TextInteractionFlag.TextSelectableByMouse |
                                              Qt.TextInteractionFlag.TextSelectableByKeyboard)
            message.exec()
            return
        self.context = db, column, overwrite, len(selected)
        try:
            self.worker = FetchDates(self.gui, source, username, identifiers, self.history)
        except Exception as err:
            error_dialog(self.gui, "Несовместимый LiveLib Metadata",
                         "Не удалось создать загрузчик. Обновите оба плагина.\n" + str(err), show=True)
            return
        self.history = self.worker.history
        self.progress = QProgressDialog('Загрузка дат из LiveLib…', 'Отмена', 0, 0, self.gui)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.canceled.connect(self.cancel)
        self.worker.finished.connect(self.finish)
        self.worker.start()
        self.progress.show()

    def cancel(self):
        if self.worker is not None:
            self.worker.abort.set()
            self.progress.setLabelText("Отмена… Ожидание завершения текущего запроса.")
            self.progress.setCancelButton(None)
            self.progress.show()

    def shutdown(self):
        self.closing = True
        if self.worker is not None:
            self.worker.abort.set()
            self.worker.wait()

    def finish(self):
        worker, self.worker = self.worker, None
        self.progress.reset()
        db, column, overwrite, total = self.context
        try:
            if self.closing or worker.abort.is_set():
                return
            if self.gui.current_db.new_api is not db:
                error_dialog(self.gui, 'Библиотека изменилась', 'Даты не сохранены. Повторите загрузку.', show=True)
                return
            if worker.failure:
                error_dialog(self.gui, 'Не удалось загрузить даты', worker.failure, show=True)
                return
            report = {}
            changed = apply_dates(db, column, worker.values, worker.identifiers, overwrite, report)
            if changed:
                self.gui.library_view.model().refresh_ids(changed)
            summary = 'Обновлено: %d из %d.\nУже совпадают с LiveLib: %d.' % (
                len(changed), total, report['unchanged'])
            if report['preserved']:
                summary += '\nСохранены прежние даты (перезапись выключена): %d.' % report['preserved']
            counts = [
                ('Без ID LiveLib', total - len(worker.identifiers)),
                ('Дата отсутствует', worker.skipped['absent']),
                ('Дата не распознана', worker.skipped['invalid']),
                ('Книга удалена или её ID изменился', report['changed_book']),
                ('Данные не получены: обход не завершён', worker.skipped['incomplete']),
            ]
            for label, count in counts:
                if count:
                    summary += '\n%s: %d.' % (label, count)
            if worker.lookup_status != 'complete':
                summary += '\n%s: %s. Найденные даты сохранены.' % (
                    'Сбой загрузки' if worker.lookup_status == 'error' else 'Обход не завершён',
                    worker.lookup_reason)
            info_dialog(self.gui, 'Даты прочтения LiveLib', summary,
                        det_msg=worker.log_output.getvalue(), show=True)
        except Exception as err:
            error_dialog(self.gui, 'Не удалось сохранить даты', str(err), show=True)
        finally:
            worker.deleteLater()
