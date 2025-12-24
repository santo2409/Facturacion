from pathlib import Path

import polars as pl
from fastexcel import read_excel


class ExcelFile:
    def __init__(self, path: Path):
        self.path = path
        self._wb = read_excel(path)

    @property
    def sheet_names(self) -> list[str]:
        return self._wb.sheet_names


class ExcelLoader:
    def load(self, path: Path) -> ExcelFile:
        return ExcelFile(path)

    def load_sheet(self, excel: ExcelFile, sheet: str):
        return pl.read_excel(
            excel.path,
            sheet_name=sheet,
            read_options={"dtypes": pl.Utf8},
            engine="calamine",
            infer_schema_length=0,
        )
