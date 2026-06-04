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
