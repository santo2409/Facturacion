from dataclasses import dataclass


@dataclass(frozen=True)
class RedirectAssignment:
    """Empresa redirigida a facturarse bajo otro NIT en la corrida actual."""

    etiqueta: str
    nit_original: str
    name_original: str
    nit_destino: str
    name_final: str
    rows: int = 1
