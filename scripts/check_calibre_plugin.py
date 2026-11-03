"""Run with calibre-debug -e scripts/check_calibre_plugin.py -- ZIP_PATH [PREVIOUS_ZIP].

Set CALIBRE_CONFIG_DIRECTORY to an isolated test directory before running.
Uses real Calibre classes and ZIP loading, but synthetic service responses and a
recording cover downloader. Tests write preferences only in that test profile.
"""
import json
import os
from queue import Queue
import sys
from threading import Event
from unittest.mock import Mock

from calibre.customize.zipplugin import loader
from calibre.utils.logging import Log
from calibre.gui2.metadata.basic_widgets import RatingEdit
from calibre.gui2.metadata.single import MetadataSingleDialogBase
from qt.core import QApplication, QCheckBox, QComboBox, QLineEdit


def main(path, previous_path=None):
    if not os.environ.get('CALIBRE_CONFIG_DIRECTORY'):
        raise SystemExit('Set CALIBRE_CONFIG_DIRECTORY to an isolated test profile first')
    # Calibre may preload an installed copy while importing customize. Ensure
    # submodules come from the ZIP under test, not that installed version.
    for name in tuple(sys.modules):
        if name == 'calibre_plugins.livelib_metadata' or name.startswith('calibre_plugins.livelib_metadata.'):
            del sys.modules[name]
    if previous_path:
        previous = loader.load(previous_path)(None)
        assert previous.version < (0, 5, 0)
        assert 'calibre_plugins.livelib_metadata.identifiers' in sys.modules
        # Keep the previous modules loaded, as Preferences -> Load plugin from
        # file does when replacing an installed plugin in a running Calibre.
    plugin = loader.load(path)(None)
    assert plugin.version == (0, 5, 0)
    assert type(plugin).__module__ == 'calibre_plugins.livelib_metadata'
    # Use an isolated CALIBRE_CONFIG_DIRECTORY when running this script.
    # Exercise Calibre's real generated widget and JSONConfig persistence.
    app = QApplication.instance() or QApplication([])
    widget = plugin.config_widget()
    switches = {w.opt.name: w for w in widget.widgets if isinstance(w, QCheckBox)}
    assert set(switches) == {'use_litres', 'use_livelib', 'use_fantlab'}
    assert all(w.isChecked() for w in switches.values())
    username = next(w for w in widget.widgets if isinstance(w, QLineEdit)
                    and w.opt.name == 'livelib_username')
    assert username.text() == ''
    fallback = next(w for w in widget.widgets if isinstance(w, QComboBox)
                    and w.opt.name == 'livelib_rating_fallback')
    assert fallback.currentData() == 'none'
    assert {fallback.itemText(i) for i in range(fallback.count())} == {
        'Использовать общую оценку книги', 'Не переносить оценку'}
    fallback.setCurrentIndex(fallback.findData('public'))
    assert type(plugin)(None).prefs['livelib_rating_fallback'] == 'none'
    username.setText('example_reader')
    assert type(plugin)(None).prefs['livelib_username'] == ''
    switches['use_litres'].setChecked(False)
    # Discarding a widget must not commit its changes.
    assert type(plugin)(None).prefs['use_litres'] is True
    plugin.save_settings(widget)
    assert type(plugin)(None).prefs['use_litres'] is False
    assert type(plugin)(None).prefs['livelib_username'] == 'example_reader'
    assert type(plugin)(None).prefs['livelib_rating_fallback'] == 'public'
    restored = plugin.config_widget()
    assert next(w for w in restored.widgets if isinstance(w, QComboBox)
                and w.opt.name == 'livelib_rating_fallback').currentData() == 'public'
    fallback.setCurrentIndex(fallback.findData('none'))
    username.setText('')
    switches['use_litres'].setChecked(True)
    plugin.save_settings(widget)
    assert type(plugin)(None).prefs['livelib_rating_fallback'] == 'none'
    plugin.prefs['ignore_fields'] = ['tags']
    widget = plugin.config_widget()
    plugin.save_settings(widget)
    assert plugin.prefs['ignore_fields'] == ['tags']
    plugin.prefs['ignore_fields'] = []
    from calibre_plugins.livelib_metadata.html_utils import safe_html_fromstring
    unicode_text = '\U0001f600' * 2048
    unicode_page = '<html><head><title>Книга</title></head><body><p>' + unicode_text + '</p></body></html>'
    root = safe_html_fromstring(unicode_page)
    assert root.xpath('//title/text()') == ['Книга']
    assert root.xpath('//p/text()') == [unicode_text]
    log = Log()
    abort = Event()
    calls = []
    book = {'@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'},
            'isbn': '9785170906309', 'description': 'Аннотация',
            'image': {'@type': 'ImageObject',
                      'url': 'https://s1.livelib.ru/boocover/22/200x300/ab/cover.jpg'}}
    card = '<script type="application/ld+json">%s</script>' % json.dumps(book)
    search = '<div><a href="/book/22">Книга</a><a href="/author/1">Автор</a></div>'
    def text(url, timeout):
        calls.append(url)
        if 'api.fantlab.ru' in url:
            return json.dumps({'works': [{'id': 33, 'url': 'https://fantlab.ru/work33',
                'name': 'Книга', 'type': 'work', 'creators': {'authors': [{'name': 'Автор'}]},
                'image': '/cover.jpg'}]})
        return card if '/book/' in url else search
    def data(url, timeout):
        calls.append(url)
        item = {'id': 11, 'title': 'Книга', 'persons': [{'role': 'author', 'full_name': 'Автор'}]}
        return {'payload': {'data': [item] if '/search?' in url else item}}
    plugin.transport.fetch_fantlab_json = lambda url, timeout: json.loads(text(url, timeout))
    plugin.transport.fetch_livelib_text = text
    plugin.transport.fetch_litres_json = data
    for identifiers in ({}, {'litres': '11'}, {'livelib': '22'}, {'fantlab': 'work33'}):
        queue = Queue()
        plugin.identify(log, queue, abort, title='Книга', authors=['Автор'], identifiers=identifiers)
        found = [queue.get_nowait() for _ in range(queue.qsize())]
        assert len(found) == (3 if not identifiers else 1)
        assert all(mi.title == 'Книга' for mi in found)
        assert all(mi.identifiers == {'litres': '11', 'livelib': '22',
                                     'fantlab': 'work33', 'isbn': '9785170906309'} for mi in found)
        assert all(mi.isbn == '9785170906309' for mi in found)
        assert len(plugin.get_book_urls(found[0].identifiers)) == 3
    plugin.prefs['livelib_username'] = 'example_reader'
    plugin.transport.post_form_json = Mock(return_value={
        'error_code': 0, 'last_page': True,
        'content': '<div class="brow-h2"><h2>Октябрь 2026 г.</h2></div>'
                   '<div class="book-item-manage"><a class="brow-book-name" href="/book/22-title">Книга</a>'
                   '<div class="brow-ratings"><span class="rating-value">4</span></div></div>',
    })
    queue = Queue()
    plugin.identify(log, queue, abort, title='Книга', authors=['Автор'])
    assert queue.qsize() == 3
    while not queue.empty():
        mi = queue.get_nowait()
        assert mi.rating == 4
        assert 'Моя оценка LiveLib: 4 / 5' in mi.comments
        assert 'Дата прочтения LiveLib: Октябрь 2026 г.' in mi.comments
        assert mi.comments.count('Детали издания LiveLib:') == 1
        # Exercise Calibre's actual download-to-editor conversion, which
        # doubles the source's 0..5 rating before storing it in the widget.
        editor = Mock()
        editor.focusWidget.return_value = None
        editor.rating = RatingEdit(None)
        editor.tags.current_val = []
        editor.identifiers.current_val = {}
        MetadataSingleDialogBase.update_from_mi(editor, mi, update_sorts=False)
        assert editor.rating.current_val == 8  # Four stars, not a clamped five.
    plugin.transport.post_form_json.assert_called_once()
    plugin.prefs['livelib_username'] = ''
    downloader = Mock()
    plugin.download_multiple_covers = downloader
    plugin.download_cover(log, Queue(), abort, title='Книга', authors=['Автор'], get_best_cover=True)
    urls = downloader.call_args.args[2]
    assert len(urls) == 4, urls
    assert downloader.call_args.args[3] is True
    assert plugin.get_cached_cover_url({'litres': '11'})
    plugin.prefs['use_litres'] = False
    plugin.prefs['use_livelib'] = False
    plugin.prefs['use_fantlab'] = False
    before = len(calls)
    queue = Queue()
    plugin.identify(log, queue, abort, title='Книга', identifiers={'litres': '11'})
    plugin.download_cover(log, queue, abort, title='Книга', identifiers={'litres': '11'})
    assert queue.empty() and len(calls) == before
    assert plugin.get_cached_cover_url({'litres': '11'}) is None
    for key in ('use_litres', 'use_livelib', 'use_fantlab'):
        plugin.prefs[key] = True
    abort.set()
    queue = Queue()
    before = len(calls)
    plugin.identify(log, queue, abort, identifiers={'litres': '11'})
    assert queue.empty() and len(calls) == before
    other = type(plugin)(None)
    assert other.get_cached_cover_url({'litres': '11'}) is None
    print('PASS: real Calibre ZIP, native settings widget and persistence, personal rating/date, multiple IDs, '
          'direct IDs, ISBN enrichment, links, covers, disabled sources, cancellation, isolation')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
