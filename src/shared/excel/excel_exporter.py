import re
from pathlib import Path

import polars as pl
from xlsxwriter import Workbook

from src.shared.console.progress import RichProgress

INVALID_SHEET_CHARS = re.compile(r"[\[\]\:\*\?\/\\]")
EXCEL_MAX_ROWS = 1_048_576
MAX_DATA_ROWS_PER_SHEET = EXCEL_MAX_ROWS - 1


def sanitize_sheet_name(name: str) -> str:
    return INVALID_SHEET_CHARS.sub("_", name)[:31]


class ExcelExporter:
    def __init__(self, progress: RichProgress = None):
        self.progress = progress

    def export_dataframes(self, dataframes: dict[str, pl.DataFrame], output_path: Path):
        if output_path.is_dir():
            output_path = output_path / "facturacion_normalizada.xlsx"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook(str(output_path))

        chunks = []
        for sheet_name, df in dataframes.items():
            chunks.extend(self._split_into_sheets(sheet_name, df))

        try:
            with self.progress(description="Exportando a Excel", total=len(chunks)):
                for sheet_name, df in chunks:
                    self._write_sheet(workbook, sheet_name, df)
                    self.progress.advance()

        finally:
            workbook.close()

    def _split_into_sheets(self, sheet_name: str, df: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
        if df.height <= MAX_DATA_ROWS_PER_SHEET:
            return [(sheet_name, df)]

        chunks = []
        for i, start in enumerate(range(0, df.height, MAX_DATA_ROWS_PER_SHEET), start=1):
            name = sheet_name if i == 1 else f"{sheet_name}_{i}"
            chunks.append((name, df.slice(start, MAX_DATA_ROWS_PER_SHEET)))
        return chunks

    def _write_sheet(self, workbook: Workbook, sheet_name: str, df: pl.DataFrame):
        safe_name = sanitize_sheet_name(sheet_name)
        worksheet = workbook.add_worksheet(safe_name)

        rows, cols = df.shape
        last_row = rows
        last_col = cols - 1

        # Escribir encabezados
        worksheet.write_row(0, 0, df.columns)

        # Escribir datos por columnas
        for col_idx, col in enumerate(df.columns):
            worksheet.write_column(1, col_idx, df.get_column(col).to_list())

        # Definir tabla Excel
        worksheet.add_table(
            0,
            0,
            last_row,
            last_col,
            {
                "columns": [{"header": c} for c in df.columns],
                "style": "Table Style Medium 9",
            },
        )

        # Ajuste visual
        worksheet.freeze_panes(1, 0)
