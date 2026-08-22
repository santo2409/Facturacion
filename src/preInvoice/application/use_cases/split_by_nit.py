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

# Colores de fase usados en assigned_rates (sin prefijo alpha "00")
_PHASE_COLORS_6 = {
    "FFF2CC",  # Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)
    "F4B183",  # Fase 3 — Cualquier paquete (mismo CUP, misma ciudad)
    "BDD7EE",  # Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)
    "9DC3E6",  # Fase 5 — Cualquier paquete (CUP base, misma ciudad)
    "D5A6E6",  # Fase 6 — Cualquier paquete/ciudad (cup + actividad)
    "FFB6C1",  # Fase 7 — Cualquier paquete, otra ciudad
}

# openpyxl almacena colores con prefijo alpha "00"
_PHASE_COLORS_ARGB = {f"00{c}" for c in _PHASE_COLORS_6}

_PHASE_LEGEND = [
    ("FFF2CC", "Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)"),
    ("F4B183", "Fase 3 — Cualquier paquete (mismo CUP, misma ciudad)"),
    ("BDD7EE", "Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)"),
    ("9DC3E6", "Fase 5 — Cualquier paquete (CUP base, misma ciudad)"),
    ("D5A6E6", "Fase 6 — Cualquier paquete/ciudad (cup + actividad)"),
    ("FFB6C1", "Fase 7 — Cualquier paquete, otra ciudad"),
]


class SplitByNit:
    def __init__(self, logger, cup_repo: CupRepository | None = None, progress=None):
        self.logger = logger
        self.cup_repo = cup_repo
        self.progress = progress

    def execute(self, source_path: Path, output_dir: Path):
        # Cargar SIN read_only para acceder a formatos de celda
        wb_src = openpyxl.load_workbook(source_path, data_only=True)
        ws_src = wb_src["Consolidado"]

        # Extraer valores y colores de fase simultáneamente
        all_rows = []
        # cell_colors[(data_row_idx, col_idx)] → color hex 6 chars (sin alpha)
        cell_colors: dict[tuple[int, int], str] = {}

        for row_idx, row in enumerate(ws_src.iter_rows()):
            row_values = [cell.value for cell in row]
            all_rows.append(tuple(row_values))

            # Solo filas de datos (skip header en row_idx=0)
            if row_idx >= 1:
                data_idx = row_idx - 1
                for col_idx, cell in enumerate(row):
                    color = self._extract_phase_color(cell)
                    if color:
                        cell_colors[(data_idx, col_idx)] = color

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
        # Cada fila se almacena como tupla (data_row_idx_original, row_list)
        groups: dict[str, dict] = defaultdict(lambda: defaultdict(list))
        for data_idx, row_tuple in enumerate(data_rows):
            row = list(row_tuple) + [None] * (num_cols - len(row_tuple))
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
                facturas_str = str(facturas_val).strip() if facturas_val is not None else ""
                has_set = any(
                    f.strip().upper().startswith("SET")
                    for f in facturas_str.split(",")
                    if f.strip()
                )
                dest = "GENERAL" if has_set else "General sin factura"
            else:
                dest = fact_val
            groups[dest][nit_val].append((data_idx, row))

        total_nits = sum(len(nits) for nits in groups.values())
        self.logger.info(
            f"Carpetas destino: {len(groups)}, NITs: {total_nits}",
            user_msg=f"Se encontraron {len(groups)} carpetas destino y {total_nits} NITs.",
        )

        # Nullificar 'Fecha Ingreso' para archivos de 'General sin factura'
        fecha_ingreso_idx = self._find_column_index(header, "Fecha Ingreso")
        if "General sin factura" in groups and fecha_ingreso_idx is not None:
            for nit, indexed_rows in groups["General sin factura"].items():
                for _, row in indexed_rows:
                    row[fecha_ingreso_idx] = None

        # Cargar mapa de nombres CUPS una sola vez
        all_cups_codes = [str(header[i]) for i in cups_indices]
        cups_name_map = self._build_cups_name_map(all_cups_codes)

        # Proceso 1: subcarpeta por facturador, un archivo por NIT dentro
        for facturador, nit_groups in groups.items():
            fact_dir = output_dir / self._sanitize_filename(facturador)
            os.makedirs(fact_dir, exist_ok=True)

            if self.progress:
                ctx = self.progress(f"Generando pre-facturas: {facturador}", total=len(nit_groups))
                ctx.__enter__()

            for nit, indexed_rows in nit_groups.items():
                try:
                    rows_only = [row for _, row in indexed_rows]
                    active_cups = self._get_active_cups_indices(rows_only, cups_indices)
                    final_indices = fixed_indices + active_cups
                    cups_positions = set(range(len(fixed_indices), len(final_indices)))

                    header_out = [
                        header[i] if i < len(header) else None for i in final_indices
                    ]
                    names_row = self._build_names_row(
                        header_out, cups_positions, cups_name_map
                    )

                    # Construir mapa de colores para este archivo
                    row_colors = self._build_row_colors(
                        indexed_rows, final_indices, cell_colors
                    )

                    empresa_nombre = self._extract_empresa(rows_only, empresa_idx)
                    filename = self._sanitize_filename(
                        f"pre_factura_{nit}_{empresa_nombre}"
                    )

                    wb = openpyxl.Workbook()
                    ws = wb.active
                    ws.title = "BASE GENERAL"
                    self._write_sheet(
                        ws, names_row, header_out, rows_only, final_indices,
                        cups_positions, row_colors
                    )
                    self._write_legend(wb)

                    wb.save(fact_dir / f"{filename}.xlsx")
                    self.logger.info(
                        f"[{facturador}] Generado: {filename}.xlsx ({len(rows_only)} filas)",
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error procesando NIT {nit} (facturador {facturador}): {e}",
                        exc_info=True,
                    )
                if self.progress:
                    self.progress.advance()

            if self.progress:
                ctx.__exit__(None, None, None)

        self.logger.info(
            f"Proceso 1 completado: archivos por facturador en {output_dir}",
            user_msg=f"Archivos individuales generados en subcarpetas por facturador.",
        )

        # Proceso 2: libro consolidado en pre-facturas/NITs_consolidado.xlsx
        consolidado_path = output_dir / "NITs_consolidado.xlsx"

        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        sheet_names_used = {}

        if self.progress:
            ctx2 = self.progress("Generando consolidado por NIT", total=total_nits)
            ctx2.__enter__()

        for facturador, nit_groups in groups.items():
            for nit, indexed_rows in nit_groups.items():
                try:
                    rows_only = [row for _, row in indexed_rows]
                    active_cups = self._get_active_cups_indices(rows_only, cups_indices)
                    final_indices = fixed_indices + active_cups
                    cups_positions = set(range(len(fixed_indices), len(final_indices)))

                    header_out = [
                        header[i] if i < len(header) else None for i in final_indices
                    ]
                    names_row = self._build_names_row(
                        header_out, cups_positions, cups_name_map
                    )

                    row_colors = self._build_row_colors(
                        indexed_rows, final_indices, cell_colors
                    )

                    empresa_nombre = self._extract_empresa(rows_only, empresa_idx)
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
                        ws, names_row, header_out, rows_only, final_indices,
                        cups_positions, row_colors
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error en hoja consolidada NIT {nit}: {e}", exc_info=True
                    )
                if self.progress:
                    self.progress.advance()

        if self.progress:
            ctx2.__exit__(None, None, None)

        self._write_legend(wb)
        wb.save(consolidado_path)
        self.logger.info(
            f"Proceso 2 completado: libro consolidado en {consolidado_path}",
            user_msg=f"Libro consolidado generado en {consolidado_path}",
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_phase_color(cell) -> str | None:
        """Extrae el color de fase de una celda, retorna hex 6 chars o None."""
        fill = cell.fill
        if fill is None or fill.patternType is None:
            return None
        fg = fill.fgColor
        if fg is None or fg.rgb is None:
            return None
        rgb = str(fg.rgb)
        # openpyxl retorna ARGB (8 chars con alpha) o RGB (6 chars)
        if len(rgb) == 8:
            hex6 = rgb[2:]  # quitar alpha "00"
        elif len(rgb) == 6:
            hex6 = rgb
        else:
            return None
        if hex6.upper() in _PHASE_COLORS_6:
            return hex6.upper()
        return None

    @staticmethod
    def _build_row_colors(
        indexed_rows: list[tuple[int, list]],
        final_indices: list[int],
        cell_colors: dict[tuple[int, int], str],
    ) -> dict[tuple[int, int], str]:
        """
        Construye mapa (out_row_idx, out_col_idx) → hex_color para las filas de salida.
        """
        row_colors = {}
        for out_row_idx, (orig_data_idx, _) in enumerate(indexed_rows):
            for out_col_idx, orig_col_idx in enumerate(final_indices):
                color = cell_colors.get((orig_data_idx, orig_col_idx))
                if color:
                    row_colors[(out_row_idx, out_col_idx)] = color
        return row_colors

    @staticmethod
    def _write_legend(wb):
        """Agrega hoja Leyenda con los colores de fase."""
        ws = wb.create_sheet(title="Leyenda")
        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 55

        h_font = Font(name="Arial", bold=True, size=10)
        ws.cell(row=1, column=1, value="Color").font = h_font
        ws.cell(row=1, column=2, value="Significado").font = h_font

        # Fase 1: sin color (blanco)
        ws.cell(row=2, column=1, value="").fill = PatternFill("solid", fgColor="FFFFFF")
        ws.cell(row=2, column=2, value="Fase 1 — Paquete propio (sin fallback)")

        for i, (color, label) in enumerate(_PHASE_LEGEND, start=3):
            ws.cell(row=i, column=1, value="").fill = PatternFill("solid", fgColor=color)
            ws.cell(row=i, column=2, value=label)

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
        self, ws, names_row, header_out, rows, final_indices, cups_positions,
        row_colors=None
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

        # Cache de PatternFill por color para evitar crear objetos duplicados
        fill_cache: dict[str, PatternFill] = {}

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
            for col_idx, cell in enumerate(ws[r_idx + 3]):
                cell.font = d_font
                cell.alignment = d_align
                cell.border = border
                # Aplicar color de fase si existe
                if row_colors:
                    color = row_colors.get((r_idx, col_idx))
                    if color:
                        if color not in fill_cache:
                            fill_cache[color] = PatternFill("solid", fgColor=color)
                        cell.fill = fill_cache[color]

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
