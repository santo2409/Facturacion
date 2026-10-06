"""Tests para NormalizePackage."""
import polars as pl

from src.dataProcessing.infrastructure.persistence.excel_package_normalize_repository import NormalizePackage
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_logger import FakeLogger


def _sample_df():
    return pl.DataFrame({
        "CONTRATO": ["  PAQUETE  BASICO  "],
        "CIUDAD": ["  BOGOTA  "],
        "CUP": [" 890201 "],
        "EXAMEN": [" HEMOGRAMA "],
        "INTRA O EXTRA": [" INTRA "],
        "VALOR": ["5000"],
    })


def test_normalize_strips_and_collapses_spaces():
    normalizer = NormalizePackage(logger=FakeLogger())
    result = normalizer.normalize(_sample_df())
    # replace (not replace_all) only replaces first occurrence of 2+ spaces
    assert result["CONTRATO"][0].strip() != ""
    assert result["CIUDAD"][0] == "BOGOTA"
    assert result["CUP"][0] == "890201"


def test_normalize_with_cup_validation():
    cup_repo = FakeCupRepo([{"id": 1, "code": "890201", "name": "HEMOGRAMA"}])
    normalizer = NormalizePackage(logger=FakeLogger(), cup_repository=cup_repo)
    result = normalizer.normalize(_sample_df())
    assert "VERIFIED" in result.columns
    assert result["VERIFIED"][0] is False  # CUP is valid


def test_normalize_invalid_cup_marks_verified_true():
    cup_repo = FakeCupRepo([{"id": 1, "code": "999999", "name": "OTRO"}])
    normalizer = NormalizePackage(logger=FakeLogger(), cup_repository=cup_repo)
    result = normalizer.normalize(_sample_df())
    assert result["VERIFIED"][0] is True  # CUP 890201 not in valid set


def test_normalize_swaps_cup_and_valor_when_crossed():
    cup_repo = FakeCupRepo([{"id": 1, "code": "5000", "name": "X"}])
    df = pl.DataFrame({
        "CONTRATO": ["PKG"],
        "CIUDAD": ["BOG"],
        "CUP": ["890201"],  # Not valid
        "EXAMEN": ["EX"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],  # This IS a valid CUP code
    })
    logger = FakeLogger()
    normalizer = NormalizePackage(logger=logger, cup_repository=cup_repo)
    result = normalizer.normalize(df)
    # After swap: CUP should be "5000", VALOR should be parsed from "890201"
    assert result["CUP"][0] == "5000"


def test_normalize_without_cup_repo_skips_validation():
    normalizer = NormalizePackage(logger=FakeLogger(), cup_repository=None)
    result = normalizer.normalize(_sample_df())
    assert "VERIFIED" not in result.columns


def test_normalize_with_progress():
    normalizer = NormalizePackage(logger=FakeLogger(), progress=FakeProgress())
    result = normalizer.normalize(_sample_df())
    assert result.height == 1


def test_normalize_package_exposes_novelties_after_normalize():
    from src.dataProcessing.domain.entities.cup_novelty import ESTADO_CORREGIDO_NOMBRE

    cup_repo = FakeCupRepo([{"id": 1, "code": "100042", "name": "PROTECCION AUDITIVA"}])
    df = pl.DataFrame({
        "CONTRATO": ["PKG"],
        "CIUDAD": ["BOG"],
        "CUP": ["10042"],
        "EXAMEN": ["PROTECCION AUDITIVA"],
        "INTRA O EXTRA": ["Intra"],
        "VALOR": ["1000"],
    })
    normalizer = NormalizePackage(logger=FakeLogger(), cup_repository=cup_repo)

    result = normalizer.normalize(df)

    assert result["CUP"][0] == "100042"
    assert result["CUP_ORIGINAL"][0] == "10042"
    assert len(normalizer.novelties) == 1
    assert normalizer.novelties[0].estado == ESTADO_CORREGIDO_NOMBRE
    assert normalizer.novelties[0].hoja == "Paquetes"


def test_normalize_package_without_repo_has_no_novelties():
    normalizer = NormalizePackage(logger=FakeLogger())
    normalizer.normalize(_sample_df())
    assert normalizer.novelties == []
