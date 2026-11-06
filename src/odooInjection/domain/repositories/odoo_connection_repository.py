from abc import ABC, abstractmethod


class OdooConnectionRepository(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def find_product(self, code: str) -> dict | None:
        pass

    @abstractmethod
    def find_client(self, nit: str, name: str) -> tuple[int | None, str | None, str | None]:
        pass

    @abstractmethod
    def find_client_by_name(self, name: str) -> tuple[int | None, str | None, str | None]:
        pass

    @abstractmethod
    def find_clients_by_name(self, name: str, limit: int = 10) -> list[dict]:
        """Candidatos por nombre para verificación difusa.
        Retorna [{"id": int, "name": str, "vat": str}] con el vat ya normalizado."""
        pass

    @abstractmethod
    def find_clients_batch(self, nits: list[str]) -> dict[str, tuple[int, str, str]]:
        """Resuelve múltiples NITs en el menor número de llamadas posible.
        Retorna solo las claves encontradas: {nit: (id, name, "NIT")}."""
        pass

    @abstractmethod
    def find_clients_batch_checked(
        self, nits: list[str],
    ) -> tuple[dict[str, tuple[int, str, str]], set[str]]:
        """Como `find_clients_batch`, más los NIT ambiguos: aquellos cuyo resultado
        en lote podría diferir de `find_client(nit)` y deben resolverse uno a uno."""
        pass

    @abstractmethod
    def find_partner_rates_batch(self, nits: list[str]) -> list[dict]:
        """Busca empresas por `ref_num` y devuelve sus tarifas relacionadas.
        [{'nit','partner_id','name','special_id','special_name','base_id','base_name'}]
        Solo partners encontrados; special_*/base_* son None si no hay tarifa."""
        pass

    @abstractmethod
    def find_rate_lines(self, rate_ids: list[int], cup_codes: list[str]) -> list[dict]:
        """Líneas de tarifa (`account.base.rate.line`) de las tarifas dadas,
        limitadas a los CUP indicados.
        [{'rate_id','city','cup','intra','price'}]"""
        pass

    @abstractmethod
    def find_rate_info(self, rate_ids: list[int]) -> list[dict]:
        """Nombre y vigencia de las tarifas (`account.base.rate`) dadas.
        [{'rate_id','name','state','start_date','finish_date'}]
        Las fechas vacías llegan como False (convención de Odoo)."""
        pass

    @abstractmethod
    def get_nit(self, client_id: int) -> str | None:
        pass

    @abstractmethod
    def create_client(self, nit: str, name: str) -> int:
        pass

    @abstractmethod
    def find_analytic_account(self, code: str) -> int | None:
        pass

    @abstractmethod
    def find_tax(self, name: str) -> int | None:
        pass

    @abstractmethod
    def find_uom(self, name: str) -> int | None:
        pass

    @abstractmethod
    def find_date_range(self, date: str) -> int | None:
        pass

    @abstractmethod
    def create_invoice(self, vals: dict) -> int:
        pass
