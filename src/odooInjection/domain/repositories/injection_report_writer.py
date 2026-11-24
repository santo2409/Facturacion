from abc import ABC, abstractmethod
from pathlib import Path


class InjectionReportWriter(ABC):
    """Salidas de la corrida, con los nombres y formatos de ETL-Avancys."""

    @abstractmethod
    def copy_to_verificar(self, path: Path) -> None:
        """Copia un archivo ilegible a verificar/."""

    @abstractmethod
    def start_created_log(self) -> None:
        """Crea facturas_creadas.csv con su encabezado."""

    @abstractmethod
    def append_created(self, factura_id, nit, empresa: str, url: str) -> None:
        """Agrega una factura a facturas_creadas.csv."""

    @abstractmethod
    def write_books(self, resultados: list[dict], registry, url_factura) -> None:
        """Escribe log_inyeccion.xlsx, pendientes_facturador.xlsx y cuentas_por_revisar.xlsx."""
