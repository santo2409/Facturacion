import os
import re
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.cup.domain.repositories.cup_repository import CupRepository

_CUPS_RE = re.compile(r"^\d+(-\d+)?$")

FIXED_COLUMNS = [
    "Base",
    "Ingreso N°",
    "Sede",
    "Ciudad",
    "FACTURADOR",
    "Especial / General",
    "PAQUETE",
    "NIT",
    "Empresa",
    "Empresa Misión",
    "Medio de Pago",
    "Fecha Ingreso",
    "Tipo Examen",
    "Cargo",
    "Paciente",
    "N° Identificación",
    "Número de Póliza",
    "FACTURAS",
    "ORDEN, CENTRO DE COSTO, CECO, PET",
    "ORDEN, CENTRO DE COSTO, CECO, PET_1",
    "TIPO DE ACTIVIDAD",
    "Observaciones Ingreso",
    "Total",
]

_FIXED_UPPER = {c.strip().upper() for c in FIXED_COLUMNS}


class SplitByNit:
    def __init__(self, logger, cup_repo: CupRepository | None = None):
        self.logger = logger
        self.cup_repo = cup_repo

    def execute(self, source_path: Path, output_dir: Path):
        wb_src = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
        ws_src = wb_src["Consolidado"]
        all_rows = list(ws_src.iter_rows(values_only=True))
        wb_src.close()

        header = all_rows[0]
        data_rows = all_rows[1:]

        unique_columns = self._make_unique_columns(header)
        num_cols = len(unique_columns)

        nit_idx = self._find_column_index(header, "NIT")
        empresa_idx = self._find_column_index(header, "Empresa")
        total_idx = self._find_column_index(header, "Total")

        if nit_idx is None:
            raise ValueError(f"No se encontró 'NIT'. Columnas: {header}")
        if empresa_idx is None:
            raise ValueError("No se encontró 'Empresa'.")
        if total_idx is None:
            raise ValueError("No se encontró 'Total'.")

        fixed_indices = list(range(total_idx + 1))
        optional_indices = list(range(total_idx + 1, num_cols))

        groups = defaultdict(list)
        for row in data_rows:
            row = list(row) + [None] * (num_cols - len(row))
            nit_val = row[nit_idx]
            if nit_val is not None:
                groups[nit_val].append(row)

        self.logger.info(
            f"NITs encontrados: {len(groups)}",
            user_msg=f"Se encontraron {len(groups)} NITs en el consolidado.",
        )

        nits_dir = output_dir / "NITs"
        os.makedirs(nits_dir, exist_ok=True)

        # Proceso 1: Un archivo por NIT
        for nit, rows in groups.items():
            active_optional = [
                idx for idx in optional_indices
                if any(
                    r[idx] is not None
                    and str(r[idx]).strip() not in ("", "None", "null")
                    for r in rows
                )
            ]
            final_indices = fixed_indices + active_optional

            empresa_nombre = f"NIT_{nit}"
            for row in rows:
                val = row[empresa_idx]
                if val is not None and str(val).strip():
                    empresa_nombre = self._sanitize_filename(str(val).strip())
                    break

            header_out = [header[i] if i < len(header) else None for i in final_indices]

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "BASE GENERAL"
            self._write_sheet(ws, header_out, rows, final_indices)

            file_path = nits_dir / f"{empresa_nombre}.xlsx"
            wb.save(file_path)
            self.logger.info(
                f"Generado: {empresa_nombre}.xlsx ({len(rows)} filas, {len(final_indices)} cols)",
            )

        self.logger.info(
            f"Proceso 1 completado: archivos individuales en {nits_dir}",
            user_msg=f"Archivos individuales generados en {nits_dir}",
        )

        # Proceso 2: Un libro con una hoja por NIT
        consolidado_path = output_dir / "NITs_consolidado.xlsx"
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        sheet_names_used = {}

        for nit, rows in groups.items():
            active_optional = [
                idx for idx in optional_indices
                if any(
                    r[idx] is not None
                    and str(r[idx]).strip() not in ("", "None", "null")
                    for r in rows
                )
            ]
            final_indices = fixed_indices + active_optional

            empresa_nombre = f"NIT_{nit}"
            for row in rows:
                val = row[empresa_idx]
                if val is not None and str(val).strip():
                    empresa_nombre = self._sanitize_sheetname(str(val).strip())
                    break
            else:
                empresa_nombre = self._sanitize_sheetname(empresa_nombre)

            base_name = empresa_nombre
            if base_name in sheet_names_used:
                sheet_names_used[base_name] += 1
                suffix = f"_{sheet_names_used[base_name]}"
                empresa_nombre = base_name[: 31 - len(suffix)] + suffix
            else:
                sheet_names_used[base_name] = 0

            header_out = [header[i] if i < len(header) else None for i in final_indices]

            ws = wb.create_sheet(title=empresa_nombre)
            self._write_sheet(ws, header_out, rows, final_indices)

        wb.save(consolidado_path)
        self.logger.info(
            f"Proceso 2 completado: libro consolidado en {consolidado_path}",
            user_msg=f"Libro consolidado generado en {consolidado_path}",
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _make_unique_columns(cols):
        counts, unique = {}, []
        for col in cols:
            c = str(col) if col is not None else ""
            if c in counts:
                counts[c] += 1
                unique.append(f"{c}_{counts[c]}")
            else:
                counts[c] = 0
                unique.append(c)
        return unique

    @staticmethod
    def _find_column_index(header, name):
        for i, val in enumerate(header):
            if val is not None and str(val).strip().upper() == name.strip().upper():
                return i
        return None

    @staticmethod
    def _sanitize_filename(name):
        return re.sub(r'[\\/*?:"<>|]', "_", str(name).strip())[:100]

    @staticmethod
    def _sanitize_sheetname(name):
        return re.sub(r"[\\/*?:\[\]]", "_", str(name).strip())[:31]

    def _write_sheet(self, ws, header_out, rows, final_indices):
        thin = Side(style="thin", color="A6A6A6")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        h_font = Font(name="Arial", bold=True, size=9, color="FFFFFF")
        h_fill = PatternFill("solid", fgColor="808080")
        h_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        d_font = Font(name="Arial", size=9, color="1F1F1F")
        d_align = Alignment(horizontal="left", vertical="center")

        ws.append(header_out)
        ws.row_dimensions[1].height = 28
        for cell in ws[1]:
            cell.font = h_font
            cell.fill = h_fill
            cell.alignment = h_align
            cell.border = border

        for r_idx, row in enumerate(rows):
            ws.append([row[i] for i in final_indices])
            ws.row_dimensions[r_idx + 2].height = 16
            for cell in ws[r_idx + 2]:
                cell.font = d_font
                cell.alignment = d_align
                cell.border = border

        for col_cells in ws.columns:
            letter = get_column_letter(col_cells[0].column)
            max_len = max(
                (len(str(c.value)) for c in col_cells if c.value is not None),
                default=0,
            )
            ws.column_dimensions[letter].width = min(max(max_len + 2, 8), 40)

        ws.freeze_panes = "A2"
