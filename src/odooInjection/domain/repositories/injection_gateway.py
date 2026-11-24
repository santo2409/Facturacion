from abc import ABC, abstractmethod


class InjectionGateway(ABC):
    """Operaciones de Odoo que usa la carga de pre-facturas (paridad con ETL-Avancys)."""

    @property
    @abstractmethod
    def uid(self) -> int:
        """Usuario autenticado (la guarda anti-duplicados filtra por create_uid)."""

    @abstractmethod
    def connect(self) -> None:
        """Autentica (3 intentos). Se vuelve a llamar para reconectar tras un fallo de red."""

    @abstractmethod
    def find_partners_by_ref_num(self, valores: list[str]) -> list[dict]:
        """res.partner con ref_num en `valores`, limit 2, campos id/name/ref_num."""

    @abstractmethod
    def find_product(self, codigo: str) -> dict | None:
        """product.product por default_code (id, name, default_code, list_price)."""

    @abstractmethod
    def analytic_accounts_all(self) -> list[dict]:
        """Todas las account.analytic.account (id, name, code)."""

    @abstractmethod
    def analytic_accounts_by_code(self, codigo: str) -> list[dict]:
        """Todas las cuentas con ese code, sin limit."""

    @abstractmethod
    def analytic_account_read(self, cuenta_id: int) -> list[dict]:
        """read de una cuenta por id (name, code); lista vacía si no existe."""

    @abstractmethod
    def find_tax(self, nombre: str) -> int | None:
        """Impuesto por nombre exacto (sale/all) y, si no, ilike de los 20 primeros caracteres."""

    @abstractmethod
    def find_uom(self, nombre: str) -> int | None:
        """Unidad de medida por nombre exacto y, si no, ilike."""

    @abstractmethod
    def find_today_drafts(self, partner_id: int, journal_id: int, desde: str) -> list[dict]:
        """Borradores out_invoice del tercero y diario creados por este usuario desde `desde`."""

    @abstractmethod
    def create_invoice(self, vals: dict) -> int:
        """account.move.create; devuelve el id."""

    @abstractmethod
    def clear_due_date(self, factura_id: int) -> None:
        """write invoice_date_due=False."""

    @abstractmethod
    def update_prices(self, factura_id: int) -> None:
        """Botón "Actualizar precios" (JSON-RPC). Lanza RuntimeError con el mensaje de Odoo."""

    @abstractmethod
    def amount_total(self, factura_id: int) -> list[dict]:
        """read amount_total de la factura."""
