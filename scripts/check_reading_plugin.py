"""Run with calibre-debug -e in an isolated CALIBRE_CONFIG_DIRECTORY."""
import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

if not os.environ.get('CALIBRE_CONFIG_DIRECTORY'):
    raise SystemExit('Set an isolated CALIBRE_CONFIG_DIRECTORY')

from qt.core import QApplication, QAction
from calibre.gui2.actions import InterfaceAction
from calibre.customize.zipplugin import loader
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library import db as open_db
from calibre.utils.date import local_tz

root = Path(__file__).resolve().parents[1]
def check(condition):
    if not condition:
        raise RuntimeError('Integration check failed')

app = QApplication.instance() or QApplication([])
source = loader.load(str(root / 'dist/LiveLib.Metadata.zip'))(None)
wrapper = loader.load(str(root / 'dist/LiveLib.ReadingDates.zip'))(None)
check(wrapper.actual_plugin.endswith(':ReadingDatesAction'))
from calibre_plugins.livelib_reading_dates.ui import SettingsDialog, FetchDates, ReadingDatesAction
from calibre_plugins.livelib_reading_dates.sync import PREF_KEY, apply_dates

icon_action = SimpleNamespace(
    worker=None, history=None, qaction=QAction(None), start=lambda: None,
    shutdown=lambda: None,
    plugin_path=str(root / 'dist/LiveLib.ReadingDates.zip'))
icon_action.load_resources = lambda names: InterfaceAction.load_resources(icon_action, names)
ReadingDatesAction.genesis(icon_action)
check(not icon_action.qaction.icon().isNull())
check(not icon_action.qaction.icon().pixmap(32, 32).isNull())

with TemporaryDirectory(prefix='.test-', dir=root) as directory:
    legacy = open_db(directory)
    legacy.create_custom_column('read_date', 'Дата прочтения', 'datetime', False)
    legacy.close()
    legacy = open_db(directory)
    db = legacy.new_api
    mi = Metadata('Тестовая книга', ['Автор'])
    mi.set_identifier('livelib', '22')
    ids, _ = db.add_books([(mi, {})])
    book_id = ids[0]
    dialog = SettingsDialog(None, db, 1)
    check(dialog.column.findData('#read_date') > 0)
    check(not dialog.overwrite.isChecked())
    db.set_pref(PREF_KEY, {'read_date_column': '#read_date', 'overwrite': False})
    restored_dialog = SettingsDialog(None, db, 1)
    check(restored_dialog.column.currentData() == '#read_date')
    worker = FetchDates(None, source, 'reader', {book_id: '22'})
    query = {
        'queryKey': ['users', 'detail', 123, 'profile', 'reads', {
            'limit': 20, 'offset': 0, 'ordering': 'read_at_desc'}],
        'state': {'data': {'status': 200, 'payload': {
            'pagination': {'next_page': None}, 'data': [{
                'art_edition': {'id': 22}, 'rating': 9,
                'status_set_at': '2026-11-03T11:30:08',
                'read_date': {'year': 2026, 'month': 11, 'day': 2}}]}}},
    }
    payload = '6:' + json.dumps({'state': {'queries': [query]}})
    worker.history.transport.fetch_livelib_text = lambda *args: (
        '<script>self.__next_f.push(%s)</script>' % json.dumps([1, payload]))
    worker.history.transport.post_form_json = Mock(side_effect=RuntimeError('Unexpected legacy request'))
    worker.start()
    check(worker.wait(5000))
    check(worker.failure is None)
    check(worker.values[book_id].month == 11 and worker.values[book_id].day == 2)
    worker.history.transport.post_form_json.assert_not_called()
    worker.log.info('Reading dates completion check')
    model = Mock()
    fake = SimpleNamespace(closing=False, worker=worker, progress=SimpleNamespace(reset=lambda: None),
                           context=(db, '#read_date', False, 1),
                           gui=SimpleNamespace(current_db=SimpleNamespace(new_api=db),
                                               library_view=SimpleNamespace(model=lambda: model)))
    with patch('calibre_plugins.livelib_reading_dates.ui.info_dialog') as info, \
         patch('calibre_plugins.livelib_reading_dates.ui.error_dialog') as error:
        ReadingDatesAction.finish(fake)
        check(error.call_count == 0)
        check(info.call_count == 1)
        check('Обновлено: 1 из 1' in info.call_args.args[2])
        check('Reading dates completion check' in info.call_args.kwargs['det_msg'])
        check(model.refresh_ids.call_args.args[0] == {book_id})
        fake.worker = worker
        fake.context = (db, '#read_date', True, 1)
        ReadingDatesAction.finish(fake)
        check(error.call_count == 0)
        check('Обновлено: 0 из 1' in info.call_args.args[2])
        check('Уже совпадают с LiveLib: 1' in info.call_args.args[2])
        check('Пропущено' not in info.call_args.args[2])
    saved = db.field_for('#read_date', book_id).astimezone(local_tz)
    check((saved.year, saved.month, saved.day) == (2026, 11, 2))
    check(apply_dates(db, '#read_date', worker.values, worker.identifiers) == set())
    # Exercise the completion handler's cancellation guard before any DB write.
    worker.abort.set()
    fake = SimpleNamespace(closing=False, worker=worker, progress=SimpleNamespace(reset=lambda: None),
                           context=(db, '#read_date', True, 1))
    ReadingDatesAction.finish(fake)
    check(fake.worker is None)
    legacy.close()
    legacy = open_db(directory)
    saved = legacy.new_api.field_for('#read_date', book_id).astimezone(local_tz)
    check((saved.year, saved.month, saved.day) == (2026, 11, 2))
    check(legacy.new_api.pref(PREF_KEY)['read_date_column'] == '#read_date')
    legacy.close()
print('Reading dates: ZIP loading, Qt settings, worker, real DB persistence and cancellation passed')
