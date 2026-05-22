import polars as pl

from src.shared.excel.excel_exporter import ExcelExporter, sanitize_sheet_name
from tests.fakes.fake_progress import FakeProgress


def test_sanitize_sheet_name_removes_invalid_chars():
    assert sanitize_sheet_name("Hoja[1]") == "Hoja_1_"
    assert sanitize_sheet_name("A:B*C?D") == "A_B_C_D"


def test_sanitize_sheet_name_truncates_to_31():
    long_name = "A" * 50
    assert len(sanitize_sheet_name(long_name)) == 31


def test_export_creates_file(tmp_path):
    exporter = ExcelExporter(progress=FakeProgress())
    df = pl.DataFrame({"NIT": ["900111111"], "EMPRESA": ["A"]})
    output = tmp_path / "output.xlsx"
    exporter.export_dataframes({"Hoja1": df}, output)
    assert output.exists()


def test_export_creates_multiple_sheets(tmp_path):
    import openpyxl

    exporter = ExcelExporter(progress=FakeProgress())
    df1 = pl.DataFrame({"A": [1]})
    df2 = pl.DataFrame({"B": [2]})
    output = tmp_path / "multi.xlsx"
    exporter.export_dataframes({"Sheet1": df1, "Sheet2": df2}, output)

    wb = openpyxl.load_workbook(output, read_only=True)
    assert "Sheet1" in wb.sheetnames
    assert "Sheet2" in wb.sheetnames
    wb.close()


def test_export_to_directory_creates_default_filename(tmp_path):
    exporter = ExcelExporter(progress=FakeProgress())
    df = pl.DataFrame({"X": [1]})
    exporter.export_dataframes({"H": df}, tmp_path)
    assert (tmp_path / "facturacion_normalizada.xlsx").exists()
