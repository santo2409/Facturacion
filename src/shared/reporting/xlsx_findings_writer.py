from datetime import datetime
from pathlib import Path
from typing import Callable

import polars as pl
from xlsxwriter import Workbook

from src.shared.reporting.findings_writer import FindingsWriter


class XlsxFindingsWriter(FindingsWriter):
    """Un libro Excel por tipo de hallazgo, en una carpeta por ejecución."""

    def __init__(self, base_dir: Path, clock: Callable[[], datetime] = datetime.now):
        self._base_dir = base_dir
        self._clock = clock

    def write(
        self,
        books: dict[str, list[dict]],
        columns: dict[str, list[str]],
        extra_sheets: dict[str, dict[str, pl.DataFrame]] | None = None,
    ) -> Path | None:
        extra_sheets = extra_sheets or {}
        non_empty = {name: rows for name, rows in books.items() if rows}
        if not non_empty:
            return None

        folder = self._base_dir / self._clock().strftime("%Y-%m-%d_%H%M")
        folder.mkdir(parents=True, exist_ok=True)
        for name, rows in non_empty.items():
            df = pl.DataFrame(rows).select(columns[name])
            with Workbook(str(folder / f"{name}.xlsx")) as workbook:
                df.write_excel(
                    workbook, worksheet=name[:31], autofit=True,
                    autofilter=True, header_format={"bold": True},
                )
                for sheet, sheet_df in extra_sheets.get(name, {}).items():
                    sheet_df.write_excel(
                        workbook, worksheet=sheet[:31], autofit=True,
                        header_format={"bold": True},
                    )
        return folder
