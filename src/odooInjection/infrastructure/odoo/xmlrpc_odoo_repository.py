import time
import xmlrpc.client

from src.odooInjection.domain.repositories.odoo_connection_repository import (
    OdooConnectionRepository,
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
        for attempt in range(3):
            try:
                common = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")
                self._uid = common.authenticate(self._db, self._username, self._api_key, {})
                if not self._uid:
                    raise ConnectionError("Autenticación fallida — verifica la API Key")
                self._models = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")
                self._logger.info(f"Conectado a Odoo. UID: {self._uid}")
                return
            except Exception as e:
                if attempt < 2:
                    self._logger.warning("Reintentando conexión en 5 segundos...")
                    time.sleep(5)
                else:
                    raise e

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
        # Búsqueda exacta
        r = self._execute(
            "res.partner", "search_read",
            [[["vat", "=", nit]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if r:
            return r[0]["id"], r[0]["name"], "NIT"
        # Búsqueda con patrón (cubre cualquier dígito de verificación)
        r = self._execute(
            "res.partner", "search_read",
            [[["vat", "=like", f"{nit}%"]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if r:
            return r[0]["id"], r[0]["name"], "NIT"
        return None, None, None

    _BATCH_SIZE = 500
    _LIKE_BATCH_SIZE = 50

    def find_clients_batch(self, nits: list[str]) -> dict[str, tuple[int, str, str]]:
        unique_nits = list(dict.fromkeys(n for n in nits if n))
        found: dict[str, tuple[int, str, str]] = {}
        for i in range(0, len(unique_nits), self._BATCH_SIZE):
            chunk = unique_nits[i : i + self._BATCH_SIZE]
            try:
                found.update(self._find_clients_batch_chunk(chunk))
            except Exception as e:
                self._logger.warning(
                    f"Fallo consultando Odoo en batch para {len(chunk)} NIT(s): {e}"
                )
        return found

    def _find_clients_batch_chunk(self, nits: list[str]) -> dict[str, tuple[int, str, str]]:
        found: dict[str, tuple[int, str, str]] = {}

        try:
            rows = self._execute(
                "res.partner", "search_read",
                [[["vat", "in", nits]]],
                {"fields": ["id", "name", "vat"]},
            )
            for row in rows:
                vat = row.get("vat")
                if vat in nits and vat not in found:
                    found[vat] = (row["id"], row["name"], "NIT")
        except Exception as e:
            self._logger.warning(
                f"Fallo la búsqueda exacta de Odoo para {len(nits)} NIT(s): {e}"
            )

        pending = [n for n in nits if n not in found]
        if not pending:
            return found

        for i in range(0, len(pending), self._LIKE_BATCH_SIZE):
            sub_chunk = pending[i : i + self._LIKE_BATCH_SIZE]
            try:
                domain = ["|"] * (len(sub_chunk) - 1) + [
                    ["vat", "=like", f"{n}%"] for n in sub_chunk
                ]
                rows = self._execute(
                    "res.partner", "search_read",
                    [domain],
                    {"fields": ["id", "name", "vat"], "order": "id asc"},
                )
                for row in rows:
                    vat = row.get("vat") or ""
                    for n in sub_chunk:
                        if n not in found and vat.startswith(n):
                            found[n] = (row["id"], row["name"], "NIT")
                            break
            except Exception as e:
                self._logger.warning(
                    f"Fallo la búsqueda por patrón de Odoo para {len(sub_chunk)} NIT(s) "
                    f"(quedan pendientes para RUES): {e}"
                )
        return found

    def find_client_by_name(self, name: str) -> tuple[int | None, str | None, str | None]:
        import re
        # Quitar sufijo societario para búsqueda flexible
        base_name = re.sub(
            r"\s*(SAS|S\s*A\s*S|SA|S\s*A|LTDA|L\s*T\s*D\s*A|EU|ESP|BIC)\s*$",
            "", name.strip(), flags=re.IGNORECASE
        ).strip()
        search_term = base_name if base_name else name
        r = self._execute(
            "res.partner", "search_read",
            [[["name", "ilike", search_term]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if r:
            return r[0]["id"], r[0]["name"], "nombre"
        return None, None, None

    def get_nit(self, client_id: int) -> str | None:
        r = self._execute(
            "res.partner", "read",
            [[client_id]],
            {"fields": ["vat"]},
        )
        if r and r[0].get("vat"):
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
