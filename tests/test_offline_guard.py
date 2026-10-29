import socket
import urllib.request

import pytest

from offline_support import UnexpectedNetwork


@pytest.mark.parametrize('method', ['fetch_url', 'fetch_json'])
def test_transport_is_blocked(source, method):
    with pytest.raises(UnexpectedNetwork, match='Unexpected network'):
        getattr(source.transport, method)('https://example.invalid', 1)


def test_block_survives_plugin_exception_handlers(source, log):
    with pytest.raises(UnexpectedNetwork):
        source.litres.search_litres(log, 'Книга', ['Автор'], 1)


def test_stdlib_network_is_blocked():
    with pytest.raises(UnexpectedNetwork):
        urllib.request.urlopen('https://example.invalid')
    with pytest.raises(UnexpectedNetwork):
        socket.create_connection(('example.invalid', 443))
