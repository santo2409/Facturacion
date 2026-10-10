from abc import ABC, abstractmethod
from pathlib import Path


class FindingsWriter(ABC):
    @abstractmethod
    def write(self, books: dict[str, list[dict]], columns: dict[str, list[str]]) -> Path | None:
        """Escribe un libro por clave de `books` que tenga filas, con las columnas
        en el orden de `columns[clave]`. Devuelve la carpeta de la ejecución, o
        None si no había nada que escribir (no se crea carpeta)."""


def summarize_findings(books: dict[str, list[dict]], folder: Path | None) -> str:
    counts = [f"{name}={len(rows)}" for name, rows in books.items() if rows]
    if not counts:
        return "Sin hallazgos."
    where = f" en {folder}" if folder else ""
    return f"Hallazgos{where}: {', '.join(counts)}."
