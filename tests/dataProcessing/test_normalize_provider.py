"""Tests para NormalizeProvider."""
import polars as pl

from src.dataProcessing.infrastructure.persistence.excel_provider_normalize_repository import NormalizeProvider
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_logger import FakeLogger


def _sample_df():
    return pl.DataFrame({
        "CONTRATO": ["  PROVEEDOR  X  ", "  PROVEEDOR  X  "],
        "CIUDAD": ["  BOGOTA  ", "  MEDELLIN  "],
        "CUP": [" 890201 ", " 890301 "],
        "EXAMEN": [" HEMOGRAMA ", " PERFIL "],
        "INTRA O EXTRA": [" INTRA ", " EXTRA "],
        "VALOR": ["5000", "3000"],
    })


def test_normalize_strips_spaces():
    normalizer = NormalizeProvider(logger=FakeLogger())
    result = normalizer.normalize(_sample_df())
    assert result["CIUDAD"][0] == "BOGOTA"
    assert result["CUP"][0] == "890201"


def test_normalize_sorts_by_contrato_descending():
    normalizer = NormalizeProvider(logger=FakeLogger())
    df = pl.DataFrame({
        "CONTRATO": ["A", "B"],
        "CIUDAD": ["X", "Y"],
        "CUP": ["1", "2"],
        "EXAMEN": ["E1", "E2"],
        "INTRA O EXTRA": ["INTRA", "EXTRA"],
        "VALOR": ["100", "200"],
    })
    result = normalizer.normalize(df)
    assert result["CONTRATO"][0] == "B"


def test_normalize_with_cup_validation():
    cup_repo = FakeCupRepo([{"id": 1, "code": "890201", "name": "HEMOGRAMA"}])
    normalizer = NormalizeProvider(logger=FakeLogger(), cup_repository=cup_repo)
    result = normalizer.normalize(_sample_df())
    assert "VERIFIED" in result.columns


def test_normalize_groups_contrato_by_slug():
    normalizer = NormalizeProvider(logger=FakeLogger())
    result = normalizer.normalize(_sample_df())
    # Both rows have same slug, so CONTRATO should be unified
    contratos = result["CONTRATO"].unique().to_list()
    assert len(contratos) == 1
