from abc import ABC, abstractmethod
from pathlib import Path

FINDING_COLUMNS = [
    "NIT", "Empresa", "Paciente", "N° Identificación", "Ciudad",
    "TIPO DE ACTIVIDAD", "CUP", "Precio asignado", "Origen",
]
COMPANY_COLUMNS = ["NIT", "Empresa", "Motivo"]


class PhaseFindingsReporter(ABC):
    @abstractmethod
    def write(self, findings: dict[str, list[dict]], companies: list[dict]) -> Path | None:
        """Escribe un libro por clave de `findings` con filas y `empresas_odoo.xlsx`
        si hay `companies`. Devuelve la carpeta creada, o None si no hubo nada."""
