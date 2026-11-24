import re
import time
import xmlrpc.client

from src.odooInjection.domain.repositories.odoo_connection_repository import (
    OdooConnectionRepository,
)
from src.shared.config import get_int_env
from src.shared.utils.text_normalizer import normalize_nit

DEFAULT_ODOO_TIMEOUT_SECONDS = 180  # mismo valor que usa ETL-Avancys para Odoo


def odoo_timeout_seconds() -> int:
    """Timeout de socket para Odoo (AUD-11). Sin la variable, 180 s; con un valor
    no entero, ValueError que nombra ODOO_TIMEOUT_SECONDS."""
    return get_int_env("ODOO_TIMEOUT_SECONDS", DEFAULT_ODOO_TIMEOUT_SECONDS)


class _TimeoutTransport(xmlrpc.client.Transport):
    """Transporte XML-RPC (http) con timeout de socket (AUD-11)."""

    def __init__(self, timeout: float):
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """Transporte XML-RPC (https) con timeout de socket (AUD-11)."""

    def __init__(self, timeout: float):
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


def _transport_for(url: str, timeout: float) -> xmlrpc.client.Transport:
    if url.lower().startswith("https://"):
        return _TimeoutSafeTransport(timeout)
    return _TimeoutTransport(timeout)

_CORPORATE_SUFFIX_RE = re.compile(
    r"\s*(SAS|S\s*A\s*S|SA|S\s*A|LTDA|L\s*T\s*D\s*A|EU|ESP|BIC)\s*$",
    flags=re.IGNORECASE,
)


class XmlRpcOdooRepository(OdooConnectionRepository):
    def __init__(self, url: str, db: str, username: str, api_key: str, logger, config: dict):
        self._url = url
        self._db = db
        self._username = username
        self._api_key = api_key
        self._logger = logger
        self._config = config
        self._uid = None
        self._models = None
        self._cache_products = {}
        self._cache_accounts = {}
        self._cache_ranges = {}
        self._cache_taxes = {}
        self._cache_uom = {}

    def connect(self) -> None:
        timeout = odoo_timeout_seconds()
        for attempt in range(3):
            try:
                common = xmlrpc.client.ServerProxy(
                    f"{self._url}/xmlrpc/2/common", transport=_transport_for(self._url, timeout)
                )
                self._uid = common.authenticate(self._db, self._username, self._api_key, {})
                if not self._uid:
                    raise ConnectionError("Autenticación fallida — verifica la API Key")
                self._models = xmlrpc.client.ServerProxy(
                    f"{self._url}/xmlrpc/2/object", transport=_transport_for(self._url, timeout)
                )
                self._logger.info(f"Conectado a Odoo. UID: {self._uid}")
                return
            except Exception as e:
                if attempt < 2:
                    self._logger.warning("Reintentando conexión en 5 segundos...")
                    time.sleep(5)
                else:
                    raise e

    @property
    def uid(self):
        return self._uid

    def execute(self, model: str, method: str, *args, **kwargs):
        """execute_kw con la sesión actual (lo usa XmlRpcInjectionGateway)."""
        return self._execute(model, method, *args, **kwargs)

    def _execute(self, model: str, method: str, *args, **kwargs):
        return self._models.execute_kw(
            self._db, self._uid, self._api_key, model, method, *args, **kwargs
        )

    def find_product(self, code: str) -> dict | None:
        if code in self._cache_products:
            return self._cache_products[code]
        r = self._execute(
            "product.product", "search_read",
            [[["default_code", "=", code]]],
            {"fields": ["id", "name", "default_code", "list_price"], "limit": 1},
        )
        self._cache_products[code] = r[0] if r else None
        return self._cache_products[code]

    def find_client(self, nit: str, name: str) -> tuple[int | None, str | None, str | None]:
        found = self.find_clients_batch([nit])
        return found.get(nit, (None, None, None))

    _BATCH_SIZE = 500
    _LIKE_BATCH_SIZE = 50

    # Etapas de la búsqueda por documento: en Odoo el NIT vive en `ref_num`; `vat`
    # solo lo tienen algunos clientes creados recientemente. Cada etapa consulta
    # solo los NIT que las anteriores no resolvieron.
    _DOCUMENT_STAGES = (
        ("ref_num", "in"),    # exacto
        ("ref_num", "like"),  # =like nit%: espacio final o DV pegado
        ("vat", "in"),        # exacto
        ("vat", "like"),      # =like nit%: vat con DV
    )

    @staticmethod
    def _document_domain(field: str, mode: str, nits: list[str]) -> list:
        if mode == "in":
            return [[field, "in", nits]]
        return ["|"] * (len(nits) - 1) + [[field, "=like", f"{n}%"] for n in nits]

    @staticmethod
    def _matches_own_condition(raw, mode: str, nit: str) -> bool:
        """¿La consulta individual de `nit` habría traído este valor en esta etapa?"""
        if mode == "in":
            return raw == nit
        return str(raw).startswith(nit)

    def _find_partners_by_document(
        self, nits: list[str], fields: list[str], ambiguous: set[str] | None = None,
    ) -> dict[str, dict]:
        """{nit: fila de res.partner}. Una fila se acepta si `normalize_nit` del campo
        consultado coincide con el NIT pedido; gana la de menor id. Un fallo de una
        etapa se registra y no impide las siguientes. Solo lectura.

        Si se pasa `ambiguous`, se anotan ahí los NIT cuyo resultado en lote podría
        diferir de la consulta individual (AUD-34): les llegó una fila por la
        condición de otro NIT, más de un partner distinto coincide con ellos, o
        falló la consulta de su bloque en alguna etapa."""
        unique_nits = list(dict.fromkeys(n for n in nits if n))
        fields = list(dict.fromkeys([*fields, "ref_num", "vat"]))
        found: dict[str, dict] = {}
        for field, mode in self._DOCUMENT_STAGES:
            pending = [n for n in unique_nits if n not in found]
            if not pending:
                break
            size = self._BATCH_SIZE if mode == "in" else self._LIKE_BATCH_SIZE
            for i in range(0, len(pending), size):
                chunk = pending[i : i + size]
                try:
                    rows = self._execute(
                        "res.partner", "search_read",
                        [self._document_domain(field, mode, chunk)],
                        {"fields": fields, "order": "id asc"},
                    )
                except Exception as e:
                    self._logger.warning(
                        f"Fallo consultando Odoo ({field}, {mode}) para {len(chunk)} NIT(s): {e}"
                    )
                    if ambiguous is not None:
                        ambiguous.update(chunk)  # se resuelven uno a uno, como antes del lote
                    continue
                wanted = set(chunk)
                for row in rows:
                    nit = normalize_nit(row.get(field) or "")
                    if nit not in wanted:
                        continue
                    if ambiguous is not None and (
                        not self._matches_own_condition(row.get(field), mode, nit)
                        or (nit in found and found[nit]["id"] != row["id"])
                    ):
                        ambiguous.add(nit)
                    if nit not in found:
                        found[nit] = row
        return found

    @staticmethod
    def _document_of(row: dict) -> str:
        """Documento del partner: `ref_num`; si está vacío, `vat` sin DV."""
        ref_num = normalize_nit(row.get("ref_num") or "")
        if ref_num:
            return ref_num
        return normalize_nit(str(row.get("vat") or "").split("-")[0])

    def find_clients_batch(self, nits: list[str]) -> dict[str, tuple[int, str, str]]:
        rows = self._find_partners_by_document(nits, ["id", "name"])
        return {nit: (row["id"], row["name"], "NIT") for nit, row in rows.items()}

    def find_clients_batch_checked(
        self, nits: list[str],
    ) -> tuple[dict[str, tuple[int, str, str]], set[str]]:
        ambiguous: set[str] = set()
        rows = self._find_partners_by_document(nits, ["id", "name"], ambiguous)
        found = {nit: (row["id"], row["name"], "NIT") for nit, row in rows.items()}
        return found, ambiguous

    _PARTNER_RATE_FIELDS = ["id", "name", "rate_base_special_id", "rate_base_id"]

    def find_partner_rates_batch(self, nits: list[str]) -> list[dict]:
        rows = self._find_partners_by_document(nits, self._PARTNER_RATE_FIELDS)
        result = []
        for nit, row in rows.items():
            special = row.get("rate_base_special_id") or [None, None]
            base = row.get("rate_base_id") or [None, None]
            result.append({
                "nit": nit,
                "partner_id": row["id"],
                "name": row["name"],
                "special_id": special[0],
                "special_name": special[1],
                "base_id": base[0],
                "base_name": base[1],
            })
        return result

    _RATE_BATCH_SIZE = 50

    def find_rate_lines(self, rate_ids: list[int], cup_codes: list[str]) -> list[dict]:
        unique_rates = list(dict.fromkeys(r for r in rate_ids if r))
        unique_cups = list(dict.fromkeys(c for c in cup_codes if c))
        if not unique_rates or not unique_cups:
            return []

        rows: list[dict] = []
        for i in range(0, len(unique_rates), self._RATE_BATCH_SIZE):
            chunk = unique_rates[i : i + self._RATE_BATCH_SIZE]
            rows.extend(self._execute(
                "account.base.rate.line", "search_read",
                [[["base_rate_id", "in", chunk], ["product_id.default_code", "in", unique_cups]]],
                {"fields": ["base_rate_id", "city_id", "product_id", "intra", "price_unit"]},
            ))

        product_ids = list(dict.fromkeys(r["product_id"][0] for r in rows if r.get("product_id")))
        if not product_ids:
            return []
        products = self._execute(
            "product.product", "read", [product_ids], {"fields": ["default_code"]},
        )
        code_by_product = {p["id"]: p.get("default_code") for p in products}

        lines = []
        for row in rows:
            city = row.get("city_id")
            product = row.get("product_id")
            cup = code_by_product.get(product[0]) if product else None
            if not city or not cup:
                continue
            lines.append({
                "rate_id": row["base_rate_id"][0],
                "city": city[1],
                "cup": cup,
                "intra": bool(row.get("intra")),
                "price": row.get("price_unit") or 0,
            })
        return lines

    def find_rate_info(self, rate_ids: list[int]) -> list[dict]:
        unique_rates = list(dict.fromkeys(r for r in rate_ids if r))
        info: list[dict] = []
        for i in range(0, len(unique_rates), self._RATE_BATCH_SIZE):
            chunk = unique_rates[i : i + self._RATE_BATCH_SIZE]
            rows = self._execute(
                "account.base.rate", "search_read",
                [[["id", "in", chunk]]],
                {"fields": ["name", "state", "start_date", "finish_date"]},
            )
            info.extend(
                {
                    "rate_id": row["id"],
                    "name": row.get("name"),
                    "state": row.get("state"),
                    "start_date": row.get("start_date"),
                    "finish_date": row.get("finish_date"),
                }
                for row in rows
            )
        return info

    @staticmethod
    def _strip_suffix(name: str) -> str:
        """Quita el sufijo societario para una búsqueda por nombre más flexible."""
        return _CORPORATE_SUFFIX_RE.sub("", (name or "").strip()).strip()

    def find_client_by_name(self, name: str) -> tuple[int | None, str | None, str | None]:
        search_term = self._strip_suffix(name) or name
        r = self._execute(
            "res.partner", "search_read",
            [[["name", "ilike", search_term]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if r:
            return r[0]["id"], r[0]["name"], "nombre"
        return None, None, None

    def find_clients_by_name(self, name: str, limit: int = 10) -> list[dict]:
        search_term = self._strip_suffix(name) or name
        rows = self._execute(
            "res.partner", "search_read",
            [[["name", "ilike", search_term]]],
            {"fields": ["id", "name", "ref_num", "vat"], "limit": limit},
        )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "vat": self._document_of(row),
            }
            for row in rows or []
        ]

    def get_nit(self, client_id: int) -> str | None:
        r = self._execute(
            "res.partner", "read",
            [[client_id]],
            {"fields": ["ref_num", "vat"]},
        )
        if not r:
            return None
        if r[0].get("ref_num"):
            return str(r[0]["ref_num"]).strip()
        if r[0].get("vat"):
            return str(r[0]["vat"]).split("-")[0].strip()
        return None

    def create_client(self, nit: str, name: str) -> int:
        return self._execute(
            "res.partner", "create",
            [{
                "name": name,
                "vat": nit,
                "is_company": True,
                "customer_rank": 1,
                "property_account_receivable_id": self._config["cuenta_receivable"],
                "property_account_payable_id": self._config["cuenta_payable"],
            }],
        )

    def find_analytic_account(self, code: str) -> int | None:
        if code in self._cache_accounts:
            return self._cache_accounts[code]
        r = self._execute(
            "account.analytic.account", "search_read",
            [[["code", "=", code]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        self._cache_accounts[code] = r[0]["id"] if r else None
        return self._cache_accounts[code]

    def find_tax(self, name: str) -> int | None:
        if name in self._cache_taxes:
            return self._cache_taxes[name]
        r = self._execute(
            "account.tax", "search_read",
            [[["name", "=", name], ["type_tax_use", "in", ["sale", "all"]]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if not r:
            r = self._execute(
                "account.tax", "search_read",
                [[["name", "ilike", name[:20]]]],
                {"fields": ["id", "name"], "limit": 5},
            )
            if r:
                self._logger.warning(
                    f"Tax '{name}' no encontrado exacto. Candidatos: {[(x['id'], x['name']) for x in r]}"
                )
        self._cache_taxes[name] = r[0]["id"] if r else None
        return self._cache_taxes[name]

    def find_uom(self, name: str) -> int | None:
        if name in self._cache_uom:
            return self._cache_uom[name]
        r = self._execute(
            "uom.uom", "search_read",
            [[["name", "=", name]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if not r:
            r = self._execute(
                "uom.uom", "search_read",
                [[["name", "ilike", name]]],
                {"fields": ["id", "name"], "limit": 1},
            )
        self._cache_uom[name] = r[0]["id"] if r else None
        return self._cache_uom[name]

    def find_date_range(self, date: str) -> int | None:
        if date in self._cache_ranges:
            return self._cache_ranges[date]
        r = self._execute(
            "date.range", "search_read",
            [[["date_start", "<=", date], ["date_end", ">=", date]]],
            {"fields": ["id"], "limit": 1},
        )
        if not r:
            r = self._execute(
                "date.range", "search_read",
                [[]], {"fields": ["id"], "limit": 1, "order": "date_end desc"},
            )
        self._cache_ranges[date] = r[0]["id"] if r else None
        return self._cache_ranges[date]

    def create_invoice(self, vals: dict) -> int:
        return self._execute("account.move", "create", [vals])
