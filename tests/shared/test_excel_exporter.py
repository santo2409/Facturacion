import polars as pl

from src.shared.excel import excel_exporter as excel_exporter_module
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


def test_export_splits_oversized_dataframe_into_multiple_sheets(tmp_path, monkeypatch):
    import openpyxl

    monkeypatch.setattr(excel_exporter_module, "MAX_DATA_ROWS_PER_SHEET", 3)

    exporter = ExcelExporter(progress=FakeProgress())
    df = pl.DataFrame({"CONTRATO": [f"C{i}" for i in range(7)]})
    output = tmp_path / "split.xlsx"
    exporter.export_dataframes({"Sheet": df}, output)

    wb = openpyxl.load_workbook(output, read_only=True)
    assert wb.sheetnames == ["Sheet", "Sheet_2", "Sheet_3"]
    assert wb["Sheet"].max_row == 4  # header + 3 data rows
    assert wb["Sheet_2"].max_row == 4
    assert wb["Sheet_3"].max_row == 2  # header + 1 data row
    wb.close()


def test_export_does_not_split_dataframe_within_limit(tmp_path):
    import openpyxl

    exporter = ExcelExporter(progress=FakeProgress())
    df = pl.DataFrame({"CONTRATO": ["C1", "C2"]})
    output = tmp_path / "no_split.xlsx"
    exporter.export_dataframes({"Sheet": df}, output)

    wb = openpyxl.load_workbook(output, read_only=True)
    assert wb.sheetnames == ["Sheet"]
    wb.close()
