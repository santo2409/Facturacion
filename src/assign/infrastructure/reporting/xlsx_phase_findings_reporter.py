from datetime import datetime
from pathlib import Path
from typing import Callable

import polars as pl

from src.assign.domain.repositories.phase_findings_reporter import (
    BOOK_DESCRIPTIONS,
    COLUMN_HELP,
    COMPANIES_KEY,
    COMPANY_COLUMNS,
    EXPIRED_COLUMNS,
    EXPIRED_KEY,
    FINDING_COLUMNS,
    PhaseFindingsReporter,
)
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter

COMPANIES_FILENAME = COMPANIES_KEY
_NO_RATE = "Sin tarifa"
_PHASE_KEY_PREFIX = "fase_01"
_GROUP_COLUMNS = [
    "Fase", "Empresa", "NIT", "Paquete original", "Ciudad", "CUP", "TIPO DE ACTIVIDAD",
    "Precio asignado", "Tipo de fuente", "Fuente", "Ciudad efectiva", "CUP efectivo",
]
_EXPIRED_GROUP_COLUMNS = [
    "Empresa", "NIT", "Tarifa Odoo", "Tipo de tarifa", "Inicio vigencia", "Fin vigencia",
    "Estado Odoo", "Ciudad", "CUP", "TIPO DE ACTIVIDAD", "Precio asignado",
]


def _group(rows: list[dict], keys: list[str]) -> list[dict]:
    """Una fila por llave, con el número de filas del consolidado (pacientes)."""
    text_keys = [k for k in keys if k != "Precio asignado"]
    df = pl.DataFrame(rows, infer_schema_length=None).with_columns(
        pl.col(text_keys).cast(pl.Utf8, strict=False)
    )
    return (
        df.group_by(keys, maintain_order=True)
        .agg(pl.len().alias("Nº pacientes"))
        .to_dicts()
    )


def _source_label(key: str, g: dict) -> str:
    if key.startswith(_PHASE_KEY_PREFIX):
        return f"Base de datos local — {g['Tipo de fuente']}: {g['Fuente']}"
    return f"{g['Tipo de fuente']}: {g['Fuente']}"


def _phase_action(key: str, g: dict, odoo_available: bool = True) -> str:
    where = f"paquete «{g['Paquete original']}», ciudad {g['Ciudad']}, CUP {g['CUP']}, actividad {g['TIPO DE ACTIVIDAD']}"
    source = f"{g['Tipo de fuente']}: {g['Fuente']}"
    if key == "sin_resolver":
        return f"Crear tarifa en {where}: no existe en ninguna fase."
    if key.startswith(_PHASE_KEY_PREFIX):
        if not odoo_available:
            return "Ninguna por ahora: Odoo no estuvo disponible en esta ejecución y la tarifa se tomó de la base de datos local."
        return f"Cargar en Odoo la tarifa de {where}: Odoo no tiene esta tarifa y se tomó de la base de datos local."
    if key.startswith("fase_04") or key.startswith("fase_05"):
        return (
            f"Crear tarifa para el CUP {g['CUP']} en {where}. "
            f"Hoy se homologa al CUP base {g['CUP efectivo']} ({source})."
        )
    if key.startswith("fase_06"):
        return (
            f"Crear tarifa en {where}. "
            f"Hoy se usa la de {g['Ciudad efectiva']} ({source})."
        )
    return f"Crear tarifa en {where}. Hoy se usa {source}."


def _phase_book(key: str, rows: list[dict], odoo_available: bool = True) -> list[dict]:
    book = []
    for g in _group(rows, _GROUP_COLUMNS):
        unresolved = key == "sin_resolver"
        book.append({
            "Fase": g["Fase"],
            "Empresa": g["Empresa"],
            "NIT": g["NIT"],
            "Paquete original": g["Paquete original"],
            "Ciudad original": g["Ciudad"],
            "CUP original": g["CUP"],
            "Actividad": g["TIPO DE ACTIVIDAD"],
            "Tarifa asignada": _NO_RATE if unresolved else g["Precio asignado"],
            "Fuente de la tarifa": _NO_RATE if unresolved else _source_label(key, g),
            "Ciudad efectiva": g["Ciudad efectiva"],
            "CUP efectivo": g["CUP efectivo"],
            "Nº pacientes": g["Nº pacientes"],
            "Qué debe hacer el área": _phase_action(key, g, odoo_available),
        })
    return book


def _expired_book(rows: list[dict]) -> list[dict]:
    return [
        {
            "Empresa": g["Empresa"],
            "NIT": g["NIT"],
            "Tarifa Odoo": g["Tarifa Odoo"],
            "Tipo de tarifa": g["Tipo de tarifa"],
            "Inicio vigencia": g["Inicio vigencia"],
            "Fin vigencia": g["Fin vigencia"],
            "Estado Odoo": g["Estado Odoo"],
            "Ciudad": g["Ciudad"],
            "CUP": g["CUP"],
            "Actividad": g["TIPO DE ACTIVIDAD"],
            "Tarifa asignada": g["Precio asignado"],
            "Nº pacientes": g["Nº pacientes"],
            "Qué debe hacer el área": (
                f"Renovar en Odoo la tarifa «{g['Tarifa Odoo']}» ({g['Tipo de tarifa']}), "
                f"vencida el {g['Fin vigencia']}. Se asignó igual el valor {g['Precio asignado']}."
            ),
        }
        for g in _group(rows, _EXPIRED_GROUP_COLUMNS)
    ]


def _legend(name: str, columns: list[str]) -> pl.DataFrame:
    entries = [("Libro", BOOK_DESCRIPTIONS.get(name, ""))]
    entries += [(c, COLUMN_HELP.get(c, "")) for c in columns]
    return pl.DataFrame(entries, schema=["Columna", "Significado"], orient="row")


class XlsxPhaseFindingsReporter(PhaseFindingsReporter):
    """Un libro Excel por fase con hallazgos, en una carpeta por ejecución."""

    def __init__(
        self,
        base_dir: Path = Path("logs/asignar_tarifas"),
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._writer = XlsxFindingsWriter(base_dir=base_dir, clock=clock)

    def write(self, findings: dict[str, list[dict]], companies: list[dict]) -> Path | None:
        books = dict(findings)
        columns = {key: FINDING_COLUMNS for key in findings}
        if companies:
            books[COMPANIES_FILENAME] = companies
            columns[COMPANIES_FILENAME] = COMPANY_COLUMNS
        return self._writer.write(books, columns)
