"""Servidor Odoo simulado en memoria, al nivel de XML-RPC.

El golden master usa el adaptador **real** `XmlRpcOdooRepository`; lo único que se
sustituye es `xmlrpc.client.ServerProxy`, de modo que también queda caracterizada
la lógica del adaptador: búsqueda por etapas, menor id, `ilike` por nombre, `limit`,
respaldo del impuesto, etc.

Lo que se simula de Odoo (supuestos, NO verificados contra un Odoo real):
- `search_read` con dominios en notación polaca (`|` y `&`; AND implícito) y los
  operadores `=`, `!=`, `in`, `=like`, `like`, `ilike`, `<=`, `>=`, `<`, `>`.
- Campos con punto (`product_id.default_code`) sobre many2one guardados como `[id, nombre]`.
- Orden por defecto: `res.partner` por `name` (en Odoo 14 es `display_name`) y el
  resto por `id`. Se respeta `order` explícito (`"id asc"`, `"date_end desc"`).
- `read` por ids y `create` (solo `account.move`, que se registra para el snapshot).
"""

from __future__ import annotations

import copy
import re

_DEFAULT_ORDER = {"res.partner": "name asc"}


def _like_to_regex(pattern: str, case_insensitive: bool) -> re.Pattern:
    parts = []
    for ch in pattern:
        if ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return re.compile("^" + "".join(parts) + "$", re.DOTALL | (re.IGNORECASE if case_insensitive else 0))


class OdooSimulado:
    """Base de datos de Odoo en memoria: {modelo: [registro, ...]}."""

    def __init__(self, datos: dict[str, list[dict]], uid: int = 2):
        self._datos = {modelo: [dict(r) for r in filas] for modelo, filas in datos.items()}
        self.uid = uid
        self.creados: list[dict] = []  # [{"modelo", "vals", "id"}] en orden de creación
        self._siguiente_id = 9000

    # ── Protocolo XML-RPC ────────────────────────────────────────────────
    def authenticate(self, db, username, api_key, _ctx):
        return self.uid

    def execute_kw(self, db, uid, key, model, method, args=None, kwargs=None):
        args = args or []
        kwargs = kwargs or {}
        if method == "search_read":
            return self._search_read(model, args[0] if args else [], **kwargs)
        if method == "read":
            return self._read(model, args[0], kwargs.get("fields"))
        if method == "create":
            return self._create(model, args[0])
        raise NotImplementedError(f"Odoo simulado: método no soportado {model}.{method}")

    # ── Implementación ───────────────────────────────────────────────────
    def _valor(self, registro: dict, campo: str):
        if "." not in campo:
            return registro.get(campo)
        base, resto = campo.split(".", 1)
        m2o = registro.get(base)
        if not m2o:
            return None
        relacionado = self._por_id(self._modelo_de(base), m2o[0])
        return self._valor(relacionado, resto) if relacionado else None

    @staticmethod
    def _modelo_de(campo_m2o: str) -> str:
        return {"product_id": "product.product", "city_id": "res.city"}.get(campo_m2o, campo_m2o)

    def _por_id(self, modelo: str, rid: int) -> dict | None:
        return next((r for r in self._datos.get(modelo, []) if r.get("id") == rid), None)

    def _cumple_termino(self, registro: dict, termino) -> bool:
        campo, op, valor = termino
        actual = self._valor(registro, campo)
        if isinstance(actual, list) and actual and op in ("=", "in", "!="):
            actual = actual[0]  # many2one comparado por id
        if op == "=":
            return actual == valor or (valor is False and not actual)
        if op == "!=":
            return actual != valor
        if op == "in":
            return actual in valor
        if op in ("=like", "like", "ilike"):
            if actual in (None, False):
                return False
            patron = valor if op == "=like" else f"%{valor}%"
            return bool(_like_to_regex(patron, op == "ilike").match(str(actual)))
        if op in ("<=", ">=", "<", ">"):
            if actual in (None, False):
                return False
            return {"<=": actual <= valor, ">=": actual >= valor, "<": actual < valor, ">": actual > valor}[op]
        raise NotImplementedError(f"Odoo simulado: operador no soportado {op}")

    def _evaluar(self, registro: dict, dominio: list) -> bool:
        pila: list[bool] = []
        for elemento in reversed(dominio):
            if elemento == "|":
                a, b = pila.pop(), pila.pop()
                pila.append(a or b)
            elif elemento == "&":
                a, b = pila.pop(), pila.pop()
                pila.append(a and b)
            elif elemento == "!":
                pila.append(not pila.pop())
            else:
                pila.append(self._cumple_termino(registro, elemento))
        return all(pila)

    def _ordenar(self, modelo: str, filas: list[dict], order: str | None) -> list[dict]:
        order = order or _DEFAULT_ORDER.get(modelo, "id asc")
        for clausula in reversed([c.strip() for c in order.split(",")]):
            campo, *dir_ = clausula.split()
            desc = bool(dir_) and dir_[0].lower() == "desc"
            filas = sorted(filas, key=lambda r: (r.get(campo) is None, r.get(campo) or ""), reverse=desc)
        return filas

    @staticmethod
    def _proyectar(registro: dict, fields: list[str] | None) -> dict:
        if not fields:
            return copy.deepcopy(registro)
        salida = {"id": registro.get("id")}
        for f in fields:
            salida[f] = copy.deepcopy(registro.get(f, False))
        return salida

    def _search_read(self, model, domain, fields=None, limit=None, order=None, offset=0):
        filas = [r for r in self._datos.get(model, []) if self._evaluar(r, domain)]
        filas = self._ordenar(model, filas, order)[offset:]
        if limit:
            filas = filas[:limit]
        return [self._proyectar(r, fields) for r in filas]

    def _read(self, model, ids, fields=None):
        return [self._proyectar(r, fields) for i in ids if (r := self._por_id(model, i))]

    def _create(self, model, vals):
        if model != "account.move":
            raise AssertionError(f"Odoo simulado: escritura no esperada en {model}")
        self._siguiente_id += 1
        self.creados.append({"modelo": model, "vals": copy.deepcopy(vals), "id": self._siguiente_id})
        return self._siguiente_id


class ServerProxySimulado:
    """Reemplazo de `xmlrpc.client.ServerProxy`: delega en un `OdooSimulado`."""

    def __init__(self, odoo: OdooSimulado):
        self._odoo = odoo

    def __call__(self, url, *a, **k):
        return self  # common y object comparten el mismo simulador

    def authenticate(self, *args):
        return self._odoo.authenticate(*args)

    def execute_kw(self, *args):
        return self._odoo.execute_kw(*args)
