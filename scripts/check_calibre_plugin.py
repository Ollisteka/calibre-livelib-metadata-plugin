"""Run with calibre-debug -e scripts/check_calibre_plugin.py -- ZIP_PATH.

Uses real Calibre classes and ZIP loading, but synthetic service responses and a
recording cover downloader. Does not install into or modify a user's profile.
"""
import json
from queue import Queue
import sys
from threading import Event
from unittest.mock import Mock

from calibre.customize.zipplugin import loader
from calibre.utils.logging import Log


def main(path):
    plugin = loader.load(path)(None)
    log = Log()
    abort = Event()
    calls = []
    book = {'@type': 'Book', 'name': 'Книга', 'author': {'name': 'Автор'},
            'isbn': '9785170906309', 'description': 'Аннотация',
            'image': 'https://s1.livelib.ru/boocover/22/200x300/ab/cover.jpg'}
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
    plugin.transport.fetch_url = text
    plugin.transport.fetch_json = data
    for identifiers in ({}, {'litres': '11'}, {'livelib': '22'}):
        queue = Queue()
        plugin.identify(log, queue, abort, title='Книга', authors=['Автор'], identifiers=identifiers)
        found = [queue.get_nowait() for _ in range(queue.qsize())]
        assert len(found) == (3 if not identifiers else 1)
        assert all(mi.title == 'Книга' for mi in found)
        if identifiers.get('livelib'):
            assert found[0].isbn == '9785170906309'
    downloader = Mock()
    plugin.download_multiple_covers = downloader
    plugin.download_cover(log, Queue(), abort, title='Книга', authors=['Автор'], get_best_cover=True)
    urls = downloader.call_args.args[2]
    assert len(urls) == 4, urls
    assert downloader.call_args.args[3] is True
    assert plugin.get_cached_cover_url({'litres': '11'})
    abort.set()
    queue = Queue()
    before = len(calls)
    plugin.identify(log, queue, abort, identifiers={'litres': '11'})
    assert queue.empty() and len(calls) == before
    other = type(plugin)(None)
    assert other.get_cached_cover_url({'litres': '11'}) is None
    print('PASS: real Calibre ZIP, search, direct IDs, ISBN, cover handoff, cache, cancellation, isolation')


if __name__ == '__main__':
    main(sys.argv[1])
