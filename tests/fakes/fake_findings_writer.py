from pathlib import Path

from src.shared.reporting.findings_writer import FindingsWriter


class FakeFindingsWriter(FindingsWriter):
    def __init__(self):
        self.books: dict[str, list[dict]] | None = None
        self.columns: dict[str, list[str]] | None = None

    def write(self, books, columns):
        self.books = {name: rows for name, rows in books.items() if rows}
        self.columns = columns
        return Path("fake") if self.books else None
