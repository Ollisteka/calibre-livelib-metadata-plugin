"""Install minimal Calibre stubs, then load the real plugin source by file path.

This avoids importing an installed plugin or requiring Calibre. Transport is blocked
by default; tests explicitly replace it with canned responses. ``plugin_module``
exposes the loaded module, while ``source`` creates a fresh Source/cache per test.
"""
import importlib.util
import logging
from pathlib import Path
from queue import Queue
import socket
import sys
from threading import Event
import urllib.request

import pytest

from calibre_stubs import install
from offline_support import UnexpectedNetwork

install()
spec = importlib.util.spec_from_file_location(
    'plugin_under_test', Path(__file__).resolve().parents[1] / 'plugin' / '__init__.py')
loaded_plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = loaded_plugin
spec.loader.exec_module(loaded_plugin)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise UnexpectedNetwork('Unexpected network request in offline tests')
    monkeypatch.setattr(loaded_plugin, 'urlopen', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.fixture
def plugin_module():
    return loaded_plugin


@pytest.fixture
def source():
    return loaded_plugin.LiveLibMetadata()


@pytest.fixture
def log():
    return logging.getLogger('plugin-tests')


@pytest.fixture
def abort():
    return Event()


@pytest.fixture
def results():
    return Queue()
