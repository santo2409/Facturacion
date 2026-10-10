"""MegaDataFrames etiqueta cada fila con su hoja y fila de origen (spec 011, RF-04)."""
import openpyxl
import polars as pl
import pytest

from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.mega_dataframes import MegaDataFrames

_HEADER = ["CONTRATO", "CIUDAD", "CUP", "INTRA O EXTRA", "VALOR"]


def _row(contract, city="BOGOTA", cup="890201", valor="5000"):
    return [contract, city, cup, "INTRA", valor]


@pytest.fixture
def libro(tmp_path):
    path = tmp_path / "tarifas.xlsx"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheets = {
        "Paquetes": [_row("PAQUETE A"), _row("PAQUETE B", city="CALI")],
        "Proveedores": [_row("PROVEEDOR Z"), _row("TARIFA PROV")],
        "TarifasEspeciales1": [_row("GRUPO UNO")],
        "TarifasEspeciales2": [_row("GRUPO DOS"), _row("PAQUETE ESP")],
    }
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(_HEADER)
        for r in rows:
            ws.append(r)
    wb.save(path)
    loader = ExcelLoader()
    return loader, loader.load(path)


def _origin(df):
    return list(zip(df["_HOJA"].to_list(), df["_FILA"].to_list(), df["CONTRATO"].to_list()))


def test_each_row_carries_sheet_and_excel_row(libro):
    loader, excel = libro

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    assert ("Paquetes", 2, "PAQUETE A") in _origin(df)
    assert ("Paquetes", 3, "PAQUETE B") in _origin(df)
    assert ("TarifasEspeciales2", 3, "PAQUETE ESP") in _origin(df)


def test_special_sheets_keep_their_own_sheet_name(libro):
    loader, excel = libro

    df = MegaDataFrames().total_dataframe(loader, excel, "TarifasEspeciales")

    assert sorted(_origin(df)) == [
        ("TarifasEspeciales1", 2, "GRUPO UNO"),
        ("TarifasEspeciales2", 2, "GRUPO DOS"),
    ]


def test_row_numbers_survive_contract_filtering(libro):
    loader, excel = libro

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    # fila 2 de Proveedores ("PROVEEDOR Z") se filtra; la fila 3 conserva su número
    assert ("Proveedores", 3, "TARIFA PROV") in _origin(df)
    assert all(c != "PROVEEDOR Z" for _, _, c in _origin(df))


def test_origin_columns_are_typed_and_last(libro):
    loader, excel = libro

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    assert df.columns[-2:] == ["_HOJA", "_FILA"]
    assert df.schema["_FILA"] == pl.Int64
    assert df.schema["_HOJA"] == pl.Utf8


def test_existing_columns_unchanged(libro):
    loader, excel = libro

    df = MegaDataFrames().total_dataframe(loader, excel, "Ciudades")

    assert df.columns[:5] == _HEADER
    assert sorted(df["CIUDAD"].unique().to_list()) == ["BOGOTA", "CALI"]
    assert df.height == 7  # 2 paquetes + 2 proveedores + 3 especiales, sin filas fantasma


def test_missing_sheets_do_not_create_phantom_rows(tmp_path):
    path = tmp_path / "solo_paquetes.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Paquetes"
    wb.active.append(_HEADER)
    wb.active.append(_row("PAQUETE A"))
    wb.save(path)
    loader = ExcelLoader()

    df = MegaDataFrames().total_dataframe(loader, loader.load(path), "Paquetes")

    assert df.height == 1
    assert _origin(df) == [("Paquetes", 2, "PAQUETE A")]


def _libro_con(tmp_path, filas):
    """Libro con una hoja `Paquetes` escrita celda a celda (permite filas vacías)."""
    path = tmp_path / "huecos.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Paquetes"
    for numero, valores in filas.items():
        for col, valor in enumerate(valores, start=1):
            ws.cell(row=numero, column=col, value=valor)
    wb.save(path)
    loader = ExcelLoader()
    return loader, loader.load(path)


def test_blank_interior_row_does_not_shift_row_numbers(tmp_path):
    loader, excel = _libro_con(tmp_path, {
        1: _HEADER, 2: _row("PAQUETE A"), 4: _row("PAQUETE B"),  # la fila 3 queda vacía
    })

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    assert _origin(df) == [("Paquetes", 2, "PAQUETE A"), ("Paquetes", 4, "PAQUETE B")]


def test_leading_blank_rows_are_counted(tmp_path):
    loader, excel = _libro_con(tmp_path, {
        3: _HEADER, 4: _row("PAQUETE A"), 5: _row("PAQUETE B"),  # encabezado en la fila 3
    })

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    assert _origin(df) == [("Paquetes", 4, "PAQUETE A"), ("Paquetes", 5, "PAQUETE B")]


def test_row_numbers_fall_back_to_sequence_when_positions_do_not_match(tmp_path):
    loader, excel = _libro_con(tmp_path, {1: _HEADER, 2: _row("PAQUETE A"), 3: _row("PAQUETE B")})
    mega = MegaDataFrames()
    mega._rows_cache[(str(excel.path), "Paquetes")] = [2]  # inconsistente con las 2 filas leídas

    df = mega.total_dataframe(loader, excel, "Paquetes")

    assert df["_FILA"].to_list() == [2, 3]


def test_unreadable_file_falls_back_to_sequential_rows_without_failing(tmp_path):
    """Un archivo que openpyxl no puede abrir (p. ej. .xls) no debe romper la carga:
    se numera en secuencia."""
    from unittest.mock import MagicMock

    excel = MagicMock()
    excel.sheet_names = ["Paquetes"]
    excel.path = tmp_path / "no_existe.xls"
    loader = MagicMock()
    loader.load_sheet = lambda e, name: pl.DataFrame({"CONTRATO": ["PAQUETE A", "PAQUETE B"]})

    df = MegaDataFrames().total_dataframe(loader, excel, "Paquetes")

    assert df["_FILA"].to_list() == [2, 3]
    assert df["_HOJA"].to_list() == ["Paquetes", "Paquetes"]
