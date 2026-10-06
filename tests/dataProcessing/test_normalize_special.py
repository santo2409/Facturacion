"""Tests para NormalizeSpecial."""
import polars as pl

from src.dataProcessing.infrastructure.persistence.excel_special_normalize_repository import NormalizeSpecial
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_logger import FakeLogger


def _sample_df():
    return pl.DataFrame({
        "CONTRATO": ["  ESPECIAL  UNO  ", "  ESPECIAL  UNO  "],
        "CIUDAD": ["  BOGOTA  ", "  MEDELLIN  "],
        "CUP": [" 890201 ", " 890301 "],
        "EXAMEN": [" HEMOGRAMA ", " PERFIL "],
        "INTRA O EXTRA": [" INTRA ", " EXTRA "],
        "VALOR": ["5000", "7000"],
    })


def test_normalize_strips_and_collapses_spaces():
    normalizer = NormalizeSpecial(logger=FakeLogger())
    result = normalizer.normalize(_sample_df())
    assert result["CIUDAD"][0] == "BOGOTA"
    assert result["CUP"][0] == "890201"


def test_normalize_with_cup_validation():
    cup_repo = FakeCupRepo([{"id": 1, "code": "890201", "name": "HEMOGRAMA"}])
    normalizer = NormalizeSpecial(logger=FakeLogger(), cup_repository=cup_repo)
    result = normalizer.normalize(_sample_df())
    assert "VERIFIED" in result.columns
    assert result["VERIFIED"][0] is False


def test_normalize_invalid_cup_marks_verified_true():
    cup_repo = FakeCupRepo([{"id": 1, "code": "999999", "name": "OTRO"}])
    normalizer = NormalizeSpecial(logger=FakeLogger(), cup_repository=cup_repo)
    result = normalizer.normalize(_sample_df())
    assert result["VERIFIED"][0] is True


def test_normalize_groups_contrato_by_slug():
    normalizer = NormalizeSpecial(logger=FakeLogger())
    result = normalizer.normalize(_sample_df())
    # Both rows have same slug, so CONTRATO should be unified
    assert result["CONTRATO"][0] == result["CONTRATO"][1]


def test_normalize_with_progress():
    normalizer = NormalizeSpecial(logger=FakeLogger(), progress=FakeProgress())
    result = normalizer.normalize(_sample_df())
    assert result.height == 2


def test_normalize_special_exposes_novelties_after_normalize():
    from src.dataProcessing.domain.entities.cup_novelty import ESTADO_CORREGIDO_NOMBRE

    cup_repo = FakeCupRepo([{"id": 1, "code": "100042", "name": "PROTECCION AUDITIVA"}])
    df = pl.DataFrame({
        "CONTRATO": ["ESPECIAL"],
        "CIUDAD": ["BOG"],
        "CUP": ["10042"],
        "EXAMEN": ["PROTECCION AUDITIVA"],
        "INTRA O EXTRA": ["Intra"],
        "VALOR": ["1000"],
    })
    normalizer = NormalizeSpecial(logger=FakeLogger(), cup_repository=cup_repo)

    result = normalizer.normalize(df)

    assert result["CUP"][0] == "100042"
    assert len(normalizer.novelties) == 1
    assert normalizer.novelties[0].estado == ESTADO_CORREGIDO_NOMBRE
    assert normalizer.novelties[0].hoja == "TarifasEspeciales"
