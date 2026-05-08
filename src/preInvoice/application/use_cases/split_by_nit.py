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

        # Clasificar índices: fijos (en orden de FIXED_COLUMNS) y CUPS (por regex)
        fixed_indices = []
        for fc in FIXED_COLUMNS:
            idx = self._find_column_index(header, fc)
            if idx is not None:
                fixed_indices.append(idx)
            else:
                self.logger.warning(f"Columna fija '{fc}' no encontrada, se omite")

        cups_indices = [
            i
            for i, col in enumerate(unique_columns)
            if self._is_cups_column(col) and i not in fixed_indices
        ]

        nit_idx = self._find_column_index(header, "NIT")
        empresa_idx = self._find_column_index(header, "Empresa")
        facturador_idx = self._find_column_index(header, "FACTURADOR")
        facturas_idx = self._find_column_index(header, "FACTURAS")

        if nit_idx is None:
            raise ValueError(f"No se encontró 'NIT'. Columnas: {header}")
        if empresa_idx is None:
            raise ValueError("No se encontró 'Empresa'.")

        # Agrupar por carpeta destino → NIT
        # GENERAL + FACTURAS no vacía  → "GENERAL"
        # GENERAL + FACTURAS vacía     → "General sin factura"
        # Otros                        → nombre del facturador
        groups: dict[str, dict] = defaultdict(lambda: defaultdict(list))
        for row in data_rows:
            row = list(row) + [None] * (num_cols - len(row))
            nit_val = row[nit_idx]
            if nit_val is None:
                self.logger.warning("Fila sin NIT omitida")
                continue
            fact_val = (
                str(row[facturador_idx]).strip()
                if facturador_idx is not None and row[facturador_idx] is not None
                else "SIN_FACTURADOR"
            )
            if fact_val.upper() == "GENERAL":
                facturas_val = (
                    row[facturas_idx]
                    if facturas_idx is not None and facturas_idx < len(row)
                    else None
                )
                dest = (
                    "GENERAL"
                    if facturas_val is not None and str(facturas_val).strip()
                    else "General sin factura"
                )
            else:
                dest = fact_val
            groups[dest][nit_val].append(row)

        total_nits = sum(len(nits) for nits in groups.values())
        self.logger.info(
            f"Carpetas destino: {len(groups)}, NITs: {total_nits}",
            user_msg=f"Se encontraron {len(groups)} carpetas destino y {total_nits} NITs.",
        )

        # Cargar mapa de nombres CUPS una sola vez
        all_cups_codes = [str(header[i]) for i in cups_indices]
        cups_name_map = self._build_cups_name_map(all_cups_codes)

        # Proceso 1: subcarpeta por facturador, un archivo por NIT dentro
        for facturador, nit_groups in groups.items():
            fact_dir = output_dir / self._sanitize_filename(facturador)
            os.makedirs(fact_dir, exist_ok=True)

            for nit, rows in nit_groups.items():
                try:
                    active_cups = self._get_active_cups_indices(rows, cups_indices)
                    final_indices = fixed_indices + active_cups
                    cups_positions = set(range(len(fixed_indices), len(final_indices)))

                    header_out = [
                        header[i] if i < len(header) else None for i in final_indices
                    ]
                    names_row = self._build_names_row(
                        header_out, cups_positions, cups_name_map
                    )

                    empresa_nombre = self._extract_empresa(rows, empresa_idx)
                    filename = self._sanitize_filename(
                        f"pre_factura_{nit}_{empresa_nombre}"
                    )

                    wb = openpyxl.Workbook()
                    ws = wb.active
                    ws.title = "BASE GENERAL"
                    self._write_sheet(
                        ws, names_row, header_out, rows, final_indices, cups_positions
                    )

                    wb.save(fact_dir / f"{filename}.xlsx")
                    self.logger.info(
                        f"[{facturador}] Generado: {filename}.xlsx ({len(rows)} filas)",
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error procesando NIT {nit} (facturador {facturador}): {e}",
                        exc_info=True,
                    )

        self.logger.info(
            f"Proceso 1 completado: archivos por facturador en {output_dir}",
            user_msg=f"Archivos individuales generados en subcarpetas por facturador.",
        )

        # Proceso 2: libro consolidado en pre-facturas/NITs_consolidado.xlsx
        consolidado_path = output_dir / "NITs_consolidado.xlsx"

        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        sheet_names_used = {}

        for facturador, nit_groups in groups.items():
            for nit, rows in nit_groups.items():
                try:
                    active_cups = self._get_active_cups_indices(rows, cups_indices)
                    final_indices = fixed_indices + active_cups
                    cups_positions = set(range(len(fixed_indices), len(final_indices)))

                    header_out = [
                        header[i] if i < len(header) else None for i in final_indices
                    ]
                    names_row = self._build_names_row(
                        header_out, cups_positions, cups_name_map
                    )

                    empresa_nombre = self._extract_empresa(rows, empresa_idx)
                    sheet_name = self._sanitize_sheetname(empresa_nombre)

                    base_name = sheet_name
                    if base_name in sheet_names_used:
                        sheet_names_used[base_name] += 1
                        suffix = f"_{sheet_names_used[base_name]}"
                        sheet_name = base_name[: 31 - len(suffix)] + suffix
                    else:
                        sheet_names_used[base_name] = 0

                    ws = wb.create_sheet(title=sheet_name)
                    self._write_sheet(
                        ws, names_row, header_out, rows, final_indices, cups_positions
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error en hoja consolidada NIT {nit}: {e}", exc_info=True
                    )

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

    @staticmethod
    def _extract_empresa(rows, empresa_idx):
        for row in rows:
            val = row[empresa_idx]
            if val is not None and str(val).strip():
                return str(val).strip()
        return "SIN_EMPRESA"

    @staticmethod
    def _build_names_row(header_out, cups_positions, cups_name_map):
        names = []
        for i, col in enumerate(header_out):
            if i in cups_positions:
                names.append(cups_name_map.get(str(col), ""))
            else:
                names.append(None)
        return names

    def _write_sheet(
        self, ws, names_row, header_out, rows, final_indices, cups_positions
    ):
        thin = Side(style="thin", color="A6A6A6")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        n_font = Font(name="Arial", bold=True, italic=True, size=9, color="1F4E79")
        n_fill = PatternFill("solid", fgColor="D6E4F0")
        n_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        h_font = Font(name="Arial", bold=True, size=9, color="FFFFFF")
        h_fill = PatternFill("solid", fgColor="808080")
        h_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        d_font = Font(name="Arial", size=9, color="1F1F1F")
        d_align = Alignment(horizontal="left", vertical="center")

        # Fila 1: nombres descriptivos CUPS
        ws.append(names_row)
        ws.row_dimensions[1].height = 28
        for cell in ws[1]:
            cell.font = n_font
            cell.fill = n_fill
            cell.alignment = n_align
            cell.border = border

        # Fila 2: headers originales
        ws.append(header_out)
        ws.row_dimensions[2].height = 28
        for cell in ws[2]:
            cell.font = h_font
            cell.fill = h_fill
            cell.alignment = h_align
            cell.border = border

        # Fila 3+: datos
        for r_idx, row in enumerate(rows):
            ws.append([row[i] for i in final_indices])
            ws.row_dimensions[r_idx + 3].height = 16
            for cell in ws[r_idx + 3]:
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

        ws.freeze_panes = "A3"

    @staticmethod
    def _is_cups_column(col_name: str) -> bool:
        if col_name is None:
            return False
        return _CUPS_RE.match(str(col_name).strip()) is not None

    def _build_cups_name_map(self, cups_codes: list[str]) -> dict[str, str]:
        if not self.cup_repo:
            return {}
        try:
            all_cups = self.cup_repo.get_all()
        except Exception as e:
            self.logger.warning(f"Error consultando catálogo CUPS: {e}")
            return {}
        catalog = {str(c["code"]).strip(): c["name"] for c in all_cups}
        result = {}
        for code in cups_codes:
            name = catalog.get(str(code), "")
            if not name:
                self.logger.warning(f"CUPS '{code}' no encontrado en catálogo")
            result[str(code)] = name
        return result

    @staticmethod
    def _get_active_cups_indices(rows: list, cups_indices: list[int]) -> list[int]:
        active = []
        for idx in cups_indices:
            for row in rows:
                val = row[idx] if idx < len(row) else None
                if val is not None and str(val).strip() not in ("", "None", "null"):
                    active.append(idx)
                    break
        return active
