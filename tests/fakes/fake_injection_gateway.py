from src.odooInjection.domain.repositories.injection_gateway import InjectionGateway


class FakeInjectionGateway(InjectionGateway):
    """Odoo en memoria para la carga de pre-facturas. Registra las escrituras."""

    def __init__(self, partners=None, products=None, accounts=None, taxes=None, uoms=None,
                 drafts=None, price_error=None, amount=0.0, fallas_red=0):
        self.partners = list(partners or [])
        self.products = {p["default_code"]: p for p in (products or [])}
        self.accounts = list(accounts or [])
        self.taxes = dict(taxes or {})
        self.uoms = dict(uoms or {})
        self.drafts = list(drafts or [])
        self.price_error = price_error
        self.amount = amount
        self.fallas_red = fallas_red          # cuántas veces falla por red find_partners_by_ref_num
        self.creadas: list[dict] = []
        self.vencimientos_limpiados: list[int] = []
        self.precios_actualizados: list[int] = []
        self.conexiones = 0
        self._siguiente = 9000

    @property
    def uid(self) -> int:
        return 2

    def connect(self) -> None:
        self.conexiones += 1

    def find_partners_by_ref_num(self, valores):
        if self.fallas_red:
            self.fallas_red -= 1
            raise ConnectionResetError("red caída")
        return [p for p in self.partners if p["ref_num"] in valores][:2]

    def find_product(self, codigo):
        return self.products.get(codigo)

    def analytic_accounts_all(self):
        return list(self.accounts)

    def analytic_accounts_by_code(self, codigo):
        return [c for c in self.accounts if c.get("code") == codigo]

    def analytic_account_read(self, cuenta_id):
        return [{"name": c["name"], "code": c.get("code")} for c in self.accounts if c["id"] == cuenta_id]

    def find_tax(self, nombre):
        return self.taxes.get(nombre)

    def find_uom(self, nombre):
        return self.uoms.get(nombre)

    def find_today_drafts(self, partner_id, journal_id, desde):
        return [{"id": d["id"]} for d in self.drafts if d["partner_id"] == partner_id][:1]

    def create_invoice(self, vals):
        self._siguiente += 1
        self.creadas.append({"id": self._siguiente, "vals": vals})
        return self._siguiente

    def clear_due_date(self, factura_id):
        self.vencimientos_limpiados.append(factura_id)

    def update_prices(self, factura_id):
        if self.price_error:
            raise RuntimeError(self.price_error)
        self.precios_actualizados.append(factura_id)

    def amount_total(self, factura_id):
        return [{"amount_total": self.amount}]
