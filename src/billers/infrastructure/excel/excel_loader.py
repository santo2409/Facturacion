from pathlib import Path

import polars as pl
from openpyxl import load_workbook


class ExcelFile:
    def __init__(self, path: Path):
        self.path = path
        self._wb = load_workbook(path, read_only=True, data_only=True)

    @property
    def sheet_names(self) -> list[str]:
        return self._wb.sheetnames


class ExcelLoader:
    def load(self, path: Path) -> ExcelFile:
        return ExcelFile(path)

    def load_sheet(self, excel: ExcelFile, sheet: str) -> pl.DataFrame:
        return pl.read_excel(
            excel.path,
            sheet_name=sheet,
            read_options={"dtypes": pl.Utf8},
            engine="calamine",
            infer_schema_length=0,
        )
