import polars as pl
from unittest.mock import MagicMock

from src.shared.utils.mega_dataframes import MegaDataFrames


def _make_excel_and_loader(sheets_data: dict):
    """Create mock excel and loader from dict of sheet_name -> DataFrame."""
    excel = MagicMock()
    excel.sheet_names = list(sheets_data.keys())
    loader = MagicMock()
    loader.load_sheet = lambda e, name: sheets_data.get(name, pl.DataFrame())

    def _load_sheets_by_prefix(e, prefix):
        frames = [df for name, df in sheets_data.items() if name.startswith(prefix)]
        return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()

    loader.load_sheets_by_prefix = _load_sheets_by_prefix
    return excel, loader


def test_total_dataframe_paquetes():
    mega = MegaDataFrames()
    sheets = {
        "Paquetes": pl.DataFrame({"CONTRATO": ["TARIFA BASICA", "PAQUETE A"]}),
        "Proveedores": pl.DataFrame({"CONTRATO": ["TARIFA PROV", "PROVEEDOR X"]}),
        "TarifasEspeciales": pl.DataFrame({"CONTRATO": ["PAQUETE ESP"]}),
    }
    excel, loader = _make_excel_and_loader(sheets)
    result = mega.total_dataframe(loader, excel, "Paquetes")
    # Should include Paquetes + filtered Proveedores (TARIFA*) + filtered Specials (PAQUETE*)
    assert result.height >= 1
    contracts = result["CONTRATO"].to_list()
    assert all(c.startswith("TARIFA") or c.startswith("PAQUETE") for c in contracts)


def test_total_dataframe_proveedores():
    mega = MegaDataFrames()
    sheets = {
        "Paquetes": pl.DataFrame({"CONTRATO": ["PROVEEDOR EN PKG"]}),
        "Proveedores": pl.DataFrame({"CONTRATO": ["PROVEEDOR X"]}),
        "TarifasEspeciales": pl.DataFrame({"CONTRATO": ["PROVEEDOR ESP"]}),
    }
    excel, loader = _make_excel_and_loader(sheets)
    result = mega.total_dataframe(loader, excel, "Proveedores")
    contracts = result["CONTRATO"].to_list()
    assert "PROVEEDOR X" in contracts


def test_total_dataframe_tarifas_especiales():
    mega = MegaDataFrames()
    sheets = {
        "Paquetes": pl.DataFrame({"CONTRATO": ["X"]}),
        "Proveedores": pl.DataFrame({"CONTRATO": ["Y"]}),
        "TarifasEspeciales": pl.DataFrame({"CONTRATO": ["ESPECIAL UNICO", "TARIFA X", "PROVEEDOR Y"]}),
    }
    excel, loader = _make_excel_and_loader(sheets)
    result = mega.total_dataframe(loader, excel, "TarifasEspeciales")
    contracts = result["CONTRATO"].to_list()
    # Should exclude TARIFA and PROVEEDOR
    assert "ESPECIAL UNICO" in contracts
    assert "TARIFA X" not in contracts


def test_total_dataframe_empty_sheets():
    mega = MegaDataFrames()
    sheets = {}
    excel, loader = _make_excel_and_loader(sheets)
    result = mega.total_dataframe(loader, excel, "Paquetes")
    assert result.is_empty()


def test_total_dataframe_multiple_tarifas_especiales_sheets():
    mega = MegaDataFrames()
    sheets = {
        "Paquetes": pl.DataFrame({"CONTRATO": ["X"]}),
        "Proveedores": pl.DataFrame({"CONTRATO": ["Y"]}),
        "TarifasEspeciales1": pl.DataFrame({"CONTRATO": ["ESPECIAL UNO"]}),
        "TarifasEspecialesBogota": pl.DataFrame({"CONTRATO": ["ESPECIAL DOS", "TARIFA X"]}),
    }
    excel, loader = _make_excel_and_loader(sheets)
    result = mega.total_dataframe(loader, excel, "TarifasEspeciales")
    contracts = result["CONTRATO"].to_list()
    # Combines both sheets sharing the prefix and excludes TARIFA/PROVEEDOR/PAQUETE rows
    assert "ESPECIAL UNO" in contracts
    assert "ESPECIAL DOS" in contracts
    assert "TARIFA X" not in contracts
