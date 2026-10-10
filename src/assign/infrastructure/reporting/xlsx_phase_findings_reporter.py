from datetime import datetime
from pathlib import Path
from typing import Callable

from src.assign.domain.repositories.phase_findings_reporter import (
    COMPANY_COLUMNS,
    FINDING_COLUMNS,
    PhaseFindingsReporter,
)
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter

COMPANIES_FILENAME = "empresas_odoo"


class XlsxPhaseFindingsReporter(PhaseFindingsReporter):
    """Un libro Excel por fase con hallazgos, en una carpeta por ejecución."""

    def __init__(
        self,
        base_dir: Path = Path("logs/asignar_tarifas"),
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._writer = XlsxFindingsWriter(base_dir=base_dir, clock=clock)

    def write(self, findings: dict[str, list[dict]], companies: list[dict]) -> Path | None:
        books = dict(findings)
        columns = {key: FINDING_COLUMNS for key in findings}
        if companies:
            books[COMPANIES_FILENAME] = companies
            columns[COMPANIES_FILENAME] = COMPANY_COLUMNS
        return self._writer.write(books, columns)
