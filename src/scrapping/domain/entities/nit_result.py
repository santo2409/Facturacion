from dataclasses import dataclass


@dataclass
class NitResult:
    """Resultado de resolver un NIT del libro de entrada.

    `checked_bases` conserva su vocabulario histórico ("BD local", "Odoo",
    "Odoo, RUES", "RUES") porque el generador del log lo compara por igualdad
    exacta; la trazabilidad de la estrategia usada viaja en `source`.

    Los campos de novedad solo se llenan cuando hay una diferencia real frente
    al libro, de modo que `None` significa "sin novedad".
    """

    nit: int
    is_company: bool
    name: str | None = None
    checked_bases: str = ""
    source: str = ""
    nit_original: str | None = None
    name_original: str | None = None
    conflict: str = ""
    save_error: str = ""
