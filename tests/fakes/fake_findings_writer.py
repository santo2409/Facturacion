from pathlib import Path

from src.shared.reporting.findings_writer import FindingsWriter


class FakeFindingsWriter(FindingsWriter):
    def __init__(self):
        self.books: dict[str, list[dict]] | None = None
        self.columns: dict[str, list[str]] | None = None
        self.extra_sheets: dict[str, dict] | None = None

    def write(self, books, columns, extra_sheets=None):
        self.books = {name: rows for name, rows in books.items() if rows}
        self.columns = columns
        self.extra_sheets = extra_sheets
        return Path("fake") if self.books else None
