from datetime import datetime
from pathlib import Path

import polars as pl

from src.shared.reporting.findings_writer import summarize_findings
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from tests.fakes.fake_findings_writer import FakeFindingsWriter

_CLOCK = lambda: datetime(2026, 10, 10, 14, 30)  # noqa: E731
_COLUMNS = {
    "ciudad_no_existe": ["Hoja", "Fila", "CIUDAD"],
    "tarifa_vacia": ["Hoja", "Fila", "CUP"],
}


def _writer(tmp_path):
    return XlsxFindingsWriter(base_dir=tmp_path / "cargar_tarifas", clock=_CLOCK)


def test_writes_only_books_with_rows(tmp_path):
    books = {
        "ciudad_no_existe": [{"Hoja": "Paquetes", "Fila": 5, "CIUDAD": "X"}],
        "tarifa_vacia": [],
    }

    folder = _writer(tmp_path).write(books, _COLUMNS)

    assert [p.name for p in folder.iterdir()] == ["ciudad_no_existe.xlsx"]


def test_no_folder_when_nothing_to_write(tmp_path):
    result = _writer(tmp_path).write({"tarifa_vacia": []}, _COLUMNS)

    assert result is None
    assert not (tmp_path / "cargar_tarifas").exists()


def test_folder_name_uses_clock_format(tmp_path):
    folder = _writer(tmp_path).write(
        {"tarifa_vacia": [{"Hoja": "P", "Fila": 2, "CUP": "890201"}]}, _COLUMNS
    )

    assert folder == tmp_path / "cargar_tarifas" / "2026-10-10_1430"


def test_columns_follow_declared_order(tmp_path):
    row = {"CUP": "890201", "Fila": 2, "Hoja": "P", "extra": "no se escribe"}

    folder = _writer(tmp_path).write({"tarifa_vacia": [row]}, _COLUMNS)

    df = pl.read_excel(folder / "tarifa_vacia.xlsx")
    assert df.columns == ["Hoja", "Fila", "CUP"]
    assert df.row(0) == ("P", 2, "890201")


def test_writes_extra_sheet_and_header_autofilter(tmp_path):
    from openpyxl import load_workbook

    books = {"tarifa_vacia": [{"Hoja": "P", "Fila": 2, "CUP": "890201"}]}
    legend = pl.DataFrame({"Columna": ["CUP"], "Significado": ["Código del examen"]})

    folder = _writer(tmp_path).write(
        books, _COLUMNS, extra_sheets={"tarifa_vacia": {"Leyenda": legend}}
    )

    wb = load_workbook(folder / "tarifa_vacia.xlsx")
    assert wb.sheetnames == ["tarifa_vacia", "Leyenda"]
    assert list(wb["tarifa_vacia"].tables)  # tabla de Excel: trae filtros en el encabezado
    assert wb["tarifa_vacia"]["A1"].font.bold is True
    assert pl.read_excel(folder / "tarifa_vacia.xlsx", sheet_name="Leyenda").row(0) == (
        "CUP",
        "Código del examen",
    )


def test_extra_sheets_ignored_for_empty_books(tmp_path):
    legend = pl.DataFrame({"Columna": ["CUP"]})

    result = _writer(tmp_path).write(
        {"tarifa_vacia": []}, _COLUMNS, extra_sheets={"tarifa_vacia": {"Leyenda": legend}}
    )

    assert result is None


def test_summarize_without_findings():
    assert summarize_findings({"tarifa_vacia": []}, None) == "Sin hallazgos."


def test_summarize_lists_counts_and_folder():
    books = {
        "contrato_no_existe": [{}],
        "ciudad_no_existe": [],
        "tarifa_vacia": [{}, {}],
    }

    text = summarize_findings(books, Path("logs/cargar_tarifas/2026-10-10_1430"))

    assert "logs/cargar_tarifas/2026-10-10_1430" in text
    assert "contrato_no_existe=1" in text
    assert "tarifa_vacia=2" in text
    assert "ciudad_no_existe" not in text


def test_fake_keeps_only_non_empty_books():
    fake = FakeFindingsWriter()

    folder = fake.write({"a": [{"x": 1}], "b": []}, {"a": ["x"], "b": ["x"]})

    assert folder == Path("fake")
    assert fake.books == {"a": [{"x": 1}]}
    assert fake.columns == {"a": ["x"], "b": ["x"]}
    assert FakeFindingsWriter().write({"a": []}, {"a": ["x"]}) is None


def test_phase_reporter_delegates_to_generic_writer(tmp_path):
    from src.assign.domain.repositories.phase_findings_reporter import (
        COMPANY_COLUMNS,
        FINDING_COLUMNS,
    )
    from src.assign.infrastructure.reporting.xlsx_phase_findings_reporter import (
        XlsxPhaseFindingsReporter,
    )

    finding = dict.fromkeys(FINDING_COLUMNS, "x")
    company = {"NIT": "1", "Empresa": "A", "Motivo": "No encontrada en Odoo"}

    via_reporter = XlsxPhaseFindingsReporter(base_dir=tmp_path / "a", clock=_CLOCK).write(
        {"sin_resolver": [finding]}, [company]
    )
    via_writer = XlsxFindingsWriter(base_dir=tmp_path / "b", clock=_CLOCK).write(
        {"sin_resolver": [finding], "empresas_odoo": [company]},
        {"sin_resolver": FINDING_COLUMNS, "empresas_odoo": COMPANY_COLUMNS},
    )

    assert sorted(p.name for p in via_reporter.iterdir()) == sorted(p.name for p in via_writer.iterdir())
    for name in ("sin_resolver.xlsx", "empresas_odoo.xlsx"):
        assert pl.read_excel(via_reporter / name).equals(pl.read_excel(via_writer / name))
    assert hasattr(XlsxPhaseFindingsReporter(base_dir=tmp_path, clock=_CLOCK), "_writer")


def test_summarize_without_folder_lists_only_counts():
    assert summarize_findings({"tarifa_vacia": [{}]}, None) == "Hallazgos: tarifa_vacia=1."
