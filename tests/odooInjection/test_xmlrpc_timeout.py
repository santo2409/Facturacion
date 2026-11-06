"""AUD-11: el adaptador XML-RPC de Odoo usa un transporte con timeout de socket."""

import socket
import threading
import xmlrpc.client

import pytest

from src.odooInjection.infrastructure.odoo import xmlrpc_odoo_repository as repo_mod
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    DEFAULT_ODOO_TIMEOUT_SECONDS,
    XmlRpcOdooRepository,
    _TimeoutSafeTransport,
    _TimeoutTransport,
    _transport_for,
    odoo_timeout_seconds,
)


class _Logger:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def _repo(url):
    return XmlRpcOdooRepository(url=url, db="db", username="u", api_key="k", logger=_Logger(), config={})


@pytest.mark.parametrize("url, clase", [
    ("https://odoo.ejemplo", _TimeoutSafeTransport),
    ("HTTPS://odoo.ejemplo", _TimeoutSafeTransport),
    ("http://localhost:8069", _TimeoutTransport),
])
def test_transport_matches_url_scheme(url, clase):
    transport = _transport_for(url, 30)
    assert type(transport) is clase and transport.timeout == 30


def test_connect_passes_timeout_transport_default_and_env(monkeypatch):
    created = []

    class _Proxy:
        def __init__(self, url, transport=None):
            created.append((url, transport))

        def authenticate(self, *a):
            return 7

    monkeypatch.setattr(repo_mod.xmlrpc.client, "ServerProxy", _Proxy)

    monkeypatch.delenv("ODOO_TIMEOUT_SECONDS", raising=False)
    _repo("https://odoo.ejemplo").connect()
    assert [t.timeout for _, t in created] == [DEFAULT_ODOO_TIMEOUT_SECONDS] * 2 == [180, 180]
    assert [u for u, _ in created] == ["https://odoo.ejemplo/xmlrpc/2/common", "https://odoo.ejemplo/xmlrpc/2/object"]

    created.clear()
    monkeypatch.setenv("ODOO_TIMEOUT_SECONDS", "15")
    _repo("https://odoo.ejemplo").connect()
    assert [t.timeout for _, t in created] == [15, 15]


def test_invalid_timeout_env_fails_fast_without_retrying(monkeypatch):
    monkeypatch.setenv("ODOO_TIMEOUT_SECONDS", "rapido")
    monkeypatch.setattr(repo_mod.time, "sleep", lambda s: pytest.fail("no debe reintentar"))
    with pytest.raises(ValueError, match="ODOO_TIMEOUT_SECONDS"):
        _repo("http://localhost:1").connect()


def test_silent_server_raises_timeout_instead_of_hanging():
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    host, port = servidor.getsockname()
    conexiones = []
    hilo = threading.Thread(target=lambda: conexiones.append(servidor.accept()), daemon=True)
    hilo.start()  # acepta la conexión y nunca responde
    try:
        proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}/xmlrpc/2/common",
                                          transport=_transport_for(f"http://{host}:{port}", 1))
        with pytest.raises(TimeoutError):
            proxy.version()
    finally:
        for conn, _ in conexiones:
            conn.close()
        servidor.close()


def test_odoo_timeout_seconds_defaults_to_180_without_variable(monkeypatch):
    monkeypatch.delenv("ODOO_TIMEOUT_SECONDS", raising=False)
    assert odoo_timeout_seconds() == 180
