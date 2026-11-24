"""Adaptador de la carga: JSON-RPC de "Actualizar precios" (Pipeline.py:557-576)."""
import json

import pytest

from src.odooInjection.infrastructure.odoo import xmlrpc_injection_gateway as modulo


class _Repo:
    uid = 2


class _Respuesta:
    def __init__(self, cuerpo):
        self._cuerpo = json.dumps(cuerpo).encode()

    def read(self):
        return self._cuerpo


def _gateway():
    return modulo.XmlRpcInjectionGateway(_Repo(), "http://odoo.invalid", "db", "clave")


def test_gateway_update_prices_envia_el_metodo_del_boton(monkeypatch):
    enviadas = []

    def _urlopen(peticion, timeout):
        enviadas.append((peticion.full_url, json.loads(peticion.data), timeout))
        return _Respuesta({"result": None})

    monkeypatch.setattr(modulo.urllib.request, "urlopen", _urlopen)
    _gateway().update_prices(9001)
    url, payload, timeout = enviadas[0]
    assert url == "http://odoo.invalid/jsonrpc" and timeout == 180
    assert payload["params"]["args"] == ["db", 2, "clave", "account.move", "update_puchase_line_prices", [[9001]], {}]


def test_gateway_update_prices_error_de_odoo_es_runtime_error(monkeypatch):
    monkeypatch.setattr(modulo.urllib.request, "urlopen",
                        lambda *_a, **_k: _Respuesta({"error": {"data": {"message": "Falta tarifa 890201"}}}))
    with pytest.raises(RuntimeError, match="Falta tarifa 890201"):
        _gateway().update_prices(9001)
