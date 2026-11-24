"""Adaptador de Odoo para la carga de pre-facturas (paridad con ETL-Avancys).

Compone `XmlRpcOdooRepository` (conexión con 3 intentos, timeout, `find_product`,
`find_tax`, `find_uom`) y agrega las consultas propias del ETL. Las llamadas son las de
`Pipeline.py` (dominios, campos y `limit`).
"""

import json
import urllib.request

from src.odooInjection.domain.repositories.injection_gateway import InjectionGateway

_JSONRPC_TIMEOUT = 180  # Pipeline.py:572


class XmlRpcInjectionGateway(InjectionGateway):
    def __init__(self, repo, url: str, db: str, api_key: str):
        self._repo = repo
        self._url = url
        self._db = db
        self._api_key = api_key

    @property
    def uid(self) -> int:
        return self._repo.uid

    def connect(self) -> None:
        self._repo.connect()

    def _execute(self, model, method, *args):
        return self._repo.execute(model, method, *args)

    def find_partners_by_ref_num(self, valores: list[str]) -> list[dict]:
        return self._execute(
            "res.partner", "search_read",
            [[["ref_num", "in", valores]]],
            {"fields": ["id", "name", "ref_num"], "limit": 2})

    def find_product(self, codigo: str) -> dict | None:
        return self._repo.find_product(codigo)

    def analytic_accounts_all(self) -> list[dict]:
        return self._execute(
            "account.analytic.account", "search_read",
            [[]], {"fields": ["id", "name", "code"]})

    def analytic_accounts_by_code(self, codigo: str) -> list[dict]:
        return self._execute(
            "account.analytic.account", "search_read",
            [[["code", "=", codigo]]], {"fields": ["id", "name", "code"]})

    def analytic_account_read(self, cuenta_id: int) -> list[dict]:
        return self._execute(
            "account.analytic.account", "read",
            [[cuenta_id]], {"fields": ["name", "code"]})

    def find_tax(self, nombre: str) -> int | None:
        return self._repo.find_tax(nombre)

    def find_uom(self, nombre: str) -> int | None:
        return self._repo.find_uom(nombre)

    def find_today_drafts(self, partner_id: int, journal_id: int, desde: str) -> list[dict]:
        return self._execute(
            "account.move", "search_read",
            [[["move_type", "=", "out_invoice"],
              ["partner_id", "=", partner_id],
              ["journal_id", "=", journal_id],
              ["create_date", ">=", desde],
              ["state", "=", "draft"],
              ["create_uid", "=", self.uid]]],
            {"fields": ["id"], "limit": 1})

    def create_invoice(self, vals: dict) -> int:
        return self._execute("account.move", "create", [vals])

    def clear_due_date(self, factura_id: int) -> None:
        self._execute("account.move", "write", [[factura_id], {"invoice_date_due": False}])

    def update_prices(self, factura_id: int) -> None:
        """JSON-RPC porque el botón devuelve None y XML-RPC no lo serializa (Pipeline.py:557-576)."""
        payload = {
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"service": "object", "method": "execute_kw",
                       "args": [self._db, self.uid, self._api_key, "account.move",
                                "update_puchase_line_prices", [[factura_id]], {}]},
        }
        peticion = urllib.request.Request(
            self._url + "/jsonrpc", json.dumps(payload).encode(),
            {"Content-Type": "application/json"})
        respuesta = json.loads(urllib.request.urlopen(peticion, timeout=_JSONRPC_TIMEOUT).read())
        if "error" in respuesta:
            datos = respuesta["error"].get("data") or {}
            raise RuntimeError(datos.get("message") or str(respuesta["error"])[:300])

    def amount_total(self, factura_id: int) -> list[dict]:
        return self._execute("account.move", "read", [[factura_id]], {"fields": ["amount_total"]})
