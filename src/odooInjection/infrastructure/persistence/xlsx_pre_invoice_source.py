"""Lector de pre-facturas con el contrato de ETL-Avancys (`Pipeline.py:873-976`, `1682-1687`).

El ETL lee con `pd.read_excel(ruta, header=None, dtype=str)`. Facturacion no usa pandas
(D-3), así que aquí se reproduce exactamente lo que hace pandas 3.0.5 con openpyxl:
  - `load_workbook(read_only=True, data_only=True, keep_links=False)`, primera hoja;
  - cada celda como `_convert_cell` (vacía → "", error → NaN, número entero → int);
  - se recortan celdas vacías al final de cada fila y filas vacías al final de la hoja;
    las filas se rellenan hasta el mismo ancho;
  - `dtype=str`: "" y los textos de `STR_NA_VALUES` son nulos; el resto, `str(valor)`.
`tests/paridad/verificar_lector.py` compara este lector con pandas sobre una carpeta real.
"""

import math
import os
from pathlib import Path

from openpyxl import load_workbook

from src.odooInjection.domain.entities.etl_constants import (
    COLUMNAS_OPCIONALES,
    COLUMNAS_REQUERIDAS,
    RX_CODIGO_EXAMEN,
)
from src.odooInjection.domain.repositories.pre_invoice_source import PreInvoiceSource

# pandas._libs.parsers.STR_NA_VALUES (pandas 3.0.5): textos que read_excel lee como nulos.
_NA_TEXTOS = frozenset({
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND",
    "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
})
_NAN = float("nan")
_FIRMA_ZIP = b"PK\x03\x04"


def _convert_cell(cell):
    """pandas.io.excel._openpyxl.OpenpyxlReader._convert_cell."""
    if cell.value is None:
        return ""
    if cell.data_type == "e":
        return _NAN
    if cell.data_type == "n":
        val = int(cell.value)
        if val == cell.value:
            return val
        return float(cell.value)
    return cell.value


def _como_texto(v):
    """dtype=str de read_excel: None representa NaN."""
    if isinstance(v, str):
        return None if v in _NA_TEXTOS else v
    if isinstance(v, float) and math.isnan(v):
        return None
    return str(v)


def leer_hoja_como_pandas(ruta: Path) -> list[list]:
    """Equivale a `pd.read_excel(ruta, header=None, dtype=str).values.tolist()` (None = NaN)."""
    with open(ruta, "rb") as fh:
        if fh.read(4) != _FIRMA_ZIP:
            raise ValueError("Excel file format cannot be determined, you must specify an engine manually.")
    wb = load_workbook(ruta, read_only=True, data_only=True, keep_links=False)
    try:
        hoja = wb.worksheets[0]
        hoja.reset_dimensions()
        datos = []
        ultima_con_datos = -1
        for n, fila in enumerate(hoja.rows):
            convertida = [_convert_cell(c) for c in fila]
            while convertida and convertida[-1] == "":
                convertida.pop()
            if convertida:
                ultima_con_datos = n
            datos.append(convertida)
        datos = datos[: ultima_con_datos + 1]
    finally:
        wb.close()
    if datos:
        ancho = max(len(f) for f in datos)
        datos = [f + [""] * (ancho - len(f)) for f in datos]
    return [[_como_texto(v) for v in f] for f in datos]


def get_val(row: dict, col_name):
    """`get_val` del ETL (Pipeline.py:914-919)."""
    v = row.get(col_name)
    if v is None:
        return None
    v = str(v).strip()
    return None if v in ("", "nan", "NaN") else v


def a_numero(v):
    """El valor del archivo como número; si no se puede, 1 (presencia). Pipeline.py:971-976."""
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 1


class XlsxPreInvoiceSource(PreInvoiceSource):
    def __init__(self, logger):
        self._logger = logger

    def list_files(self, folder: Path) -> list[Path]:
        return sorted(
            Path(os.path.join(str(folder), f))
            for f in os.listdir(folder)
            if f.lower().endswith(".xlsx") and not f.startswith("~$")
            and "consolidado" not in f.lower()
        )

    def read(self, path: Path) -> tuple[list[dict], list[str], int]:
        headers, filas_crudas, cols_examenes = self._leer_prefactura(path)
        return self._construir_filas(headers, filas_crudas, cols_examenes), cols_examenes, len(filas_crudas)

    def _leer_prefactura(self, ruta: Path):
        datos = leer_hoja_como_pandas(ruta)
        if len(datos) < 2:
            raise IndexError("single positional indexer is out-of-bounds")
        headers = datos[1]
        filas = datos[2:]

        presentes = {str(h).strip() for h in headers if h is not None}
        faltan = [c for c in COLUMNAS_REQUERIDAS if c not in presentes]
        if faltan:
            raise ValueError(
                "La plantilla cambio: faltan las columnas " + ", ".join(faltan) +
                ". Se leen por nombre exacto en la fila 2 del Excel, asi que un "
                "cambio de mayusculas o un espacio de mas las pierde. "
                "Columnas que si trae el archivo: " +
                ", ".join(sorted(c for c in presentes
                                 if not RX_CODIGO_EXAMEN.match(c))[:30]))
        sin_opcional = [c for c in COLUMNAS_OPCIONALES if c not in presentes]
        if sin_opcional:
            self._logger.warning("  " + os.path.basename(ruta) + ": faltan columnas no "
                                 "criticas (" + ", ".join(sin_opcional) + "). La factura "
                                 "sale igual, pero se pierde esa informacion.")

        cols_examenes = []
        for nombre in headers:
            if nombre is None or str(nombre).strip() == "":
                continue
            nombre_limpio = str(nombre).strip()
            if nombre_limpio.endswith(".0"):
                nombre_limpio = nombre_limpio[:-2]
            if RX_CODIGO_EXAMEN.match(nombre_limpio):
                cols_examenes.append(nombre_limpio)
        return headers, filas, cols_examenes

    @staticmethod
    def _fila_por_nombre(headers, valores) -> dict:
        # Con encabezados repetidos, pandas devolvería una Serie; se toma la primera columna.
        fila = {}
        for h, v in zip(headers, valores):
            if h is not None and h not in fila:
                fila[h] = v
        return fila

    def _construir_filas(self, headers, filas_crudas, cols_examenes) -> list[dict]:
        # Columna de cada examen: como el ETL, quita ".0" ANTES de strip (Pipeline.py:952-959).
        col_de_examen = {}
        for col_examen in cols_examenes:
            col_match = None
            for h in headers:
                if h is not None:
                    h_limpio = str(h)
                    if h_limpio.endswith(".0"):
                        h_limpio = h_limpio[:-2]
                    if h_limpio.strip() == col_examen:
                        col_match = h
                        break
            col_de_examen[col_examen] = col_match

        filas = []
        for valores in filas_crudas:
            row = self._fila_por_nombre(headers, valores)
            col_data = {
                "Proveedor": None,
                "Ciudad": get_val(row, "Ciudad"),
                "NIT": get_val(row, "NIT"),
                "Empresa": get_val(row, "Empresa"),
                "Empresa Mision": get_val(row, "Empresa Misión"),
                "Fecha Ingreso": get_val(row, "Fecha Ingreso"),
                "Tipo Examen": get_val(row, "Tipo Examen"),
                "Cargo": get_val(row, "Cargo"),
                "Paciente": get_val(row, "Paciente"),
                "N Identificacion": get_val(row, "N° Identificación"),
                "TOTAL": 0,
                "CUENTA ANALITICA": None,
                "INTRA/EXTRA": "TRUE",
                "Observaciones Ingreso": get_val(row, "Observaciones Ingreso"),
                "Sede": get_val(row, "Sede"),
                "Ingreso": get_val(row, "Ingreso N°"),
                "Base": get_val(row, "Base"),
            }
            for col_examen in cols_examenes:
                col_match = col_de_examen[col_examen]
                v = row.get(col_match) if col_match else None
                tiene_valor = (v is not None and
                               str(v).strip() not in ("", "nan", "NaN", "0", "0.0"))
                col_data[col_examen] = a_numero(v) if tiene_valor else None
            filas.append(col_data)
        return filas
