import openpyxl
import polars as pl

from src.shared.excel.excel_loader import ExcelLoader


def test_load_returns_excel_file_with_sheet_names(tmp_path):
    path = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Hoja1"
    wb.create_sheet("Hoja2")
    wb.save(path)

    loader = ExcelLoader()
    excel = loader.load(path)
    assert "Hoja1" in excel.sheet_names
    assert "Hoja2" in excel.sheet_names


def test_load_sheet_returns_polars_dataframe(tmp_path):
    path = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(["NIT", "EMPRESA"])
    ws.append(["900111111", "EMPRESA A"])
    ws.append(["900222222", "EMPRESA B"])
    wb.save(path)

    loader = ExcelLoader()
    excel = loader.load(path)
    df = loader.load_sheet(excel, "Datos")
    assert isinstance(df, pl.DataFrame)
    assert df.height == 2
    assert "NIT" in df.columns
    assert "EMPRESA" in df.columns


def test_load_sheet_all_columns_as_string(tmp_path):
    path = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(["VALOR", "CODIGO"])
    ws.append([5000, 890201])
    wb.save(path)

    loader = ExcelLoader()
    excel = loader.load(path)
    df = loader.load_sheet(excel, "Datos")
    # All columns should be Utf8 due to infer_schema_length=0
    assert all(dtype == pl.Utf8 for dtype in df.dtypes)
