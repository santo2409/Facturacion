from abc import ABC, abstractmethod
from pathlib import Path


class PreInvoiceReaderRepository(ABC):
    @abstractmethod
    def read_files(self, directory: Path) -> tuple[list[dict], list[str]]:
        """Lee pre-facturas del directorio. Retorna (filas, columnas_examenes)."""
        pass
