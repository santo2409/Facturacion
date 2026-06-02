import os
import re
from pathlib import Path

import openpyxl

from src.odooInjection.domain.repositories.pre_invoice_reader_repository import (
    PreInvoiceReaderRepository,
)

_CUPS_RE = re.compile(r"^\d+(-\d+)?$")
NUM_COLS_FIJAS = 14


class ExcelPreInvoiceReader(PreInvoiceReaderRepository):
    def __init__(self, logger):
        self._logger = logger

    def read_files(self, directory: Path) -> tuple[list[dict], list[str]]:
        archivos = sorted(
            str(directory / f)
            for f in os.listdir(directory)
            if f.lower().endswith(".xlsx")
            and not f.startswith("~$")
            and "consolidado" not in f.lower()
        )
        if not archivos:
            return [], []

        self._logger.info(f"{len(archivos)} archivo(s) encontrado(s) en {directory}")

        todas_filas = []
        todas_cols_exam = []

        for ruta in archivos:
            try:
                filas, cols_exam = self._leer_archivo(ruta)
                todas_filas.extend(filas)
                for col in cols_exam:
                    if col not in todas_cols_exam:
                        todas_cols_exam.append(col)
            except Exception as e:
                self._logger.error(f"Error leyendo {os.path.basename(ruta)}: {e}")

        return todas_filas, todas_cols_exam

    def _leer_archivo(self, ruta: str) -> tuple[list[dict], list[str]]:
        wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if len(all_rows) < 3:
            return [], []

        # Fila 1: nombres CUPS, Fila 2: headers (códigos), Fila 3+: datos
        headers = [str(h).strip() if h is not None else "" for h in all_rows[1]]
        cols_examenes = []
        for i in range(NUM_COLS_FIJAS, len(headers)):
            code = headers[i].rstrip(".0") if headers[i].endswith(".0") else headers[i]
            if code and _CUPS_RE.match(code):
                cols_examenes.append(code)

        filas = []
        for row in all_rows[2:]:
            row_data = {}
            for i, h in enumerate(headers[:NUM_COLS_FIJAS]):
                val = row[i] if i < len(row) else None
                row_data[h] = self._clean_val(val)

            for j, code in enumerate(cols_examenes):
                idx = NUM_COLS_FIJAS + j
                val = row[idx] if idx < len(row) else None
                has_value = (
                    val is not None
                    and str(val).strip() not in ("", "nan", "NaN", "0", "0.0")
                )
                row_data[code] = 1 if has_value else None

            filas.append(row_data)

        return filas, cols_examenes

    @staticmethod
    def _clean_val(v):
        if v is None:
            return None
        s = str(v).strip()
        return None if s in ("", "nan", "NaN") else s
