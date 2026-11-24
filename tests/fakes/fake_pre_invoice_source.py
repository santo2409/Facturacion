from pathlib import Path

from src.odooInjection.domain.repositories.pre_invoice_source import PreInvoiceSource


class FakePreInvoiceSource(PreInvoiceSource):
    """archivos: {nombre: (filas, columnas_examen) | Exception}."""

    def __init__(self, archivos: dict):
        self._archivos = archivos

    def list_files(self, folder: Path) -> list[Path]:
        return [Path(folder) / n for n in sorted(self._archivos)]

    def read(self, path: Path):
        contenido = self._archivos[Path(path).name]
        if isinstance(contenido, Exception):
            raise contenido
        filas, cols = contenido
        return [dict(f) for f in filas], list(cols), len(filas)
