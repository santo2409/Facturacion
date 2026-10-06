"""Regresión: las tres hojas normalizadas (con las columnas nuevas CUP_ORIGINAL,
NOVEDAD, VERIFIED) deben poder concatenarse verticalmente en
MegaDataFrames.total_dataframe (opción 4, Cargar Tarifas) sin lanzar excepción.

Ver specs/005_correccion-cups-por-nombre/plan.md, riesgo "pl.concat en la
opción 4 exige esquemas idénticos entre las 3 hojas".
"""
import polars as pl
from unittest.mock import MagicMock

from src.dataProcessing.infrastructure.persistence.excel_package_normalize_repository import (
    NormalizePackage,
)
from src.dataProcessing.infrastructure.persistence.excel_provider_normalize_repository import (
    NormalizeProvider,
)
from src.dataProcessing.infrastructure.persistence.excel_special_normalize_repository import (
    NormalizeSpecial,
)
from src.shared.utils.mega_dataframes import MegaDataFrames
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_logger import FakeLogger


def _catalog():
    return [
        {"id": 1, "code": "100042", "name": "PROTECCION AUDITIVA"},
        {"id": 2, "code": "903868", "name": "TRIGLICERIDOS"},
    ]


def _raw_sheet(contrato_values):
    n = len(contrato_values)
    return pl.DataFrame(
        {
            "CONTRATO": contrato_values,
            "CIUDAD": ["BOGOTA"] * n,
            # mezcla de CUP valido e invalido para forzar CUP_ORIGINAL/NOVEDAD no vacios
            "CUP": (["10042", "903868"] * n)[:n],
            "EXAMEN": (["PROTECCION AUDITIVA", "TRIGLICERIDOS"] * n)[:n],
            "INTRA O EXTRA": ["Intra"] * n,
            "VALOR": ["1000"] * n,
        }
    )


def _make_excel_and_loader(sheets_data: dict):
    excel = MagicMock()
    excel.sheet_names = list(sheets_data.keys())
    loader = MagicMock()
    loader.load_sheet = lambda e, name: sheets_data.get(name, pl.DataFrame())

    def _load_sheets_by_prefix(e, prefix):
        frames = [df for name, df in sheets_data.items() if name.startswith(prefix)]
        return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()

    loader.load_sheets_by_prefix = _load_sheets_by_prefix
    return excel, loader


def _normalized_sheets():
    cup_repo = FakeCupRepo(_catalog())
    logger = FakeLogger()

    pkg = NormalizePackage(logger=logger, cup_repository=cup_repo).normalize(
        _raw_sheet(["TARIFA BASICA 2024", "PAQUETE A 2025"])
    )
    prov = NormalizeProvider(logger=logger, cup_repository=cup_repo).normalize(
        _raw_sheet(["PROVEEDOR X 2025", "PROVEEDOR Y 2025"])
    )
    spec = NormalizeSpecial(logger=logger, cup_repository=cup_repo).normalize(
        _raw_sheet(["ESPECIAL UNO 2025"])
    )
    return {"Paquetes": pkg, "Proveedores": prov, "TarifasEspeciales": spec}


def test_normalized_sheets_have_identical_schema():
    sheets = _normalized_sheets()
    schemas = {name: set(df.columns) for name, df in sheets.items()}
    assert schemas["Paquetes"] == schemas["Proveedores"] == schemas["TarifasEspeciales"]
    assert {"CUP_ORIGINAL", "NOVEDAD", "VERIFIED"} <= schemas["Paquetes"]


def test_normalized_sheets_concat_without_raising_in_mega_dataframes():
    sheets = _normalized_sheets()
    excel, loader = _make_excel_and_loader(sheets)
    mega = MegaDataFrames()

    for callback in ("Paquetes", "Proveedores", "TarifasEspeciales"):
        result = mega.total_dataframe(loader, excel, callback)
        assert isinstance(result, pl.DataFrame)
