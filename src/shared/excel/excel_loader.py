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
        df = pl.read_excel(
            excel.path,
            sheet_name=sheet,
            read_options={"dtypes": pl.Utf8},
            engine="calamine",
            infer_schema_length=0,
        )
        return df.rename({c: c.strip() for c in df.columns if c != c.strip()})

    def load_sheets_by_prefix(self, excel: ExcelFile, prefix: str) -> pl.DataFrame:
        matching_sheets = [s for s in excel.sheet_names if s.startswith(prefix)]
        if not matching_sheets:
            return pl.DataFrame()
        frames = [self.load_sheet(excel, sheet) for sheet in matching_sheets]
        return pl.concat(frames, how="vertical_relaxed")
