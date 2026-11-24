from abc import ABC, abstractmethod
from pathlib import Path


class PreInvoiceSource(ABC):
    @abstractmethod
    def list_files(self, folder: Path) -> list[Path]:
        """.xlsx del primer nivel, sin '~$' ni 'consolidado', ordenados por ruta."""

    @abstractmethod
    def read(self, path: Path) -> tuple[list[dict], list[str], int]:
        """(filas internas, columnas de examen, número de filas leídas).
        Lanza una excepción si el archivo no se puede leer o la plantilla cambió."""
