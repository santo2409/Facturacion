"""Tests para CupColumnValidator: aplica la cascada de CupResolver sobre un
DataFrame Polars completo, vectorizado. Ver specs/005_correccion-cups-por-nombre/.
"""
import polars as pl

from src.dataProcessing.domain.entities.cup_novelty import (
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_HOMOLOGADO_BASE,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
    ESTADO_NO_CORREGIDO,
    ESTADO_CRUCE_CUP_VALOR,
    FASE_NOMBRE,
)
from src.dataProcessing.infrastructure.persistence.cup_column_validator import CupColumnValidator
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_fuzz import FakeFuzz


def _catalog():
    return [
        {"id": 1, "code": "100042", "name": "PROTECCION AUDITIVA"},
        {"id": 2, "code": "903868", "name": "TRIGLICERIDOS"},
        {"id": 3, "code": "903841", "name": "GLICEMIA EN SUERO"},  # distinto a "GLICEMIA" a proposito: fuerza F2, no F1
        {"id": 4, "code": "904704", "name": "INSULINA"},
        {"id": 5, "code": "208100", "name": "COMPLEJO BTX"},
        {"id": 6, "code": "5000", "name": "X"},
    ]


def _df(rows):
    return pl.DataFrame(
        rows,
        schema={
            "CONTRATO": pl.Utf8, "CIUDAD": pl.Utf8, "CUP": pl.Utf8,
            "EXAMEN": pl.Utf8, "INTRA O EXTRA": pl.Utf8, "VALOR": pl.Utf8,
        },
    )


def test_validate_adds_cup_original_novedad_verified_columns():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([{"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "903868", "EXAMEN": "TRIGLICERIDOS", "INTRA O EXTRA": "Intra", "VALOR": "1000"}])

    result, novelties = validator.validate(df, "Paquetes")

    assert {"CUP_ORIGINAL", "NOVEDAD", "VERIFIED"} <= set(result.columns)
    assert result["CUP_ORIGINAL"][0] == "903868"
    assert result["NOVEDAD"][0] == ""
    assert result["VERIFIED"][0] is False
    assert novelties == []


def test_validate_applies_f1_correction_end_to_end_proteccion_auditiva():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([
        {"CONTRATO": "S & M", "CIUDAD": "BARRANQUILLA", "CUP": "10042", "EXAMEN": "PROTECCION AUDITIVA", "INTRA O EXTRA": "Intra", "VALOR": "195300"},
        {"CONTRATO": "S & M", "CIUDAD": "BOGOTA", "CUP": "10042", "EXAMEN": "PROTECCION AUDITIVA", "INTRA O EXTRA": "Intra", "VALOR": "172300"},
    ])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"].to_list() == ["100042", "100042"]
    assert result["CUP_ORIGINAL"].to_list() == ["10042", "10042"]
    assert result["VERIFIED"].to_list() == [False, False]
    assert all("100042" in n and "10042" in n for n in result["NOVEDAD"].to_list())
    assert len(novelties) == 1
    assert novelties[0].cup_original == "10042"
    assert novelties[0].cup_corregido == "100042"
    assert novelties[0].estado == ESTADO_CORREGIDO_NOMBRE
    assert novelties[0].fase == FASE_NOMBRE
    assert novelties[0].filas == 2
    assert novelties[0].hoja == "TarifasEspeciales"
    # VALOR is untouched by the correction (RF-16)
    assert result["VALOR"].to_list() == [195300, 172300]


def test_validate_applies_f1_correction_trigliceridos():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([{"CONTRATO": "C1", "CIUDAD": "ACACIAS", "CUP": "903717", "EXAMEN": "TRIGLICERIDOS", "INTRA O EXTRA": "Intra", "VALOR": "7400"}])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"][0] == "903868"
    assert novelties[0].estado == ESTADO_CORREGIDO_NOMBRE


def test_validate_preserves_swap_behavior():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([{"CONTRATO": "PKG", "CIUDAD": "BOG", "CUP": "890201", "EXAMEN": "EX", "INTRA O EXTRA": "Intra", "VALOR": "5000"}])

    result, novelties = validator.validate(df, "Paquetes")

    assert result["CUP"][0] == "5000"
    assert novelties[0].estado == ESTADO_CRUCE_CUP_VALOR


def test_validate_without_repository_returns_df_unchanged():
    validator = CupColumnValidator(None)
    df = _df([{"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "999", "EXAMEN": "X", "INTRA O EXTRA": "Intra", "VALOR": "1"}])

    result, novelties = validator.validate(df, "Paquetes")

    assert "VERIFIED" not in result.columns
    assert novelties == []


def test_validate_f2_coocurrence_within_same_sheet():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([
        {"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "903841", "EXAMEN": "GLICEMIA", "INTRA O EXTRA": "Intra", "VALOR": "1000"},
        {"CONTRATO": "C2", "CIUDAD": "MED", "CUP": "903841", "EXAMEN": "GLICEMIA", "INTRA O EXTRA": "Intra", "VALOR": "1200"},
        {"CONTRATO": "C3", "CIUDAD": "CALI", "CUP": "8", "EXAMEN": "GLICEMIA", "INTRA O EXTRA": "Intra", "VALOR": "900"},
    ])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"].to_list() == ["903841", "903841", "903841"]
    corrected = [n for n in novelties if n.estado == ESTADO_CORREGIDO_COOCURRENCIA]
    assert len(corrected) == 1
    assert corrected[0].cup_original == "8"
    assert corrected[0].cup_corregido == "903841"


def test_validate_f3_suffix_homologation():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([{"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "904704-1", "EXAMEN": None, "INTRA O EXTRA": "Intra", "VALOR": "1000"}])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"][0] == "904704"
    assert novelties[0].estado == ESTADO_HOMOLOGADO_BASE


def test_validate_f4_fuzzy_suggestion_does_not_change_cup():
    fuzz = FakeFuzz(override={"BENCENOTOLUENOXILENO": "COMPLEJO BTX"})
    validator = CupColumnValidator(FakeCupRepo(_catalog()), fuzz=fuzz)
    df = _df([{"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "901500-01", "EXAMEN": "BENCENOTOLUENOXILENO", "INTRA O EXTRA": "Intra", "VALOR": "1000"}])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"][0] == "901500-01"
    assert result["VERIFIED"][0] is True
    assert novelties[0].estado == ESTADO_NO_CORREGIDO_SUGERENCIA
    assert "208100" in novelties[0].detalle


def test_validate_no_resolution_marks_verified_true():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([{"CONTRATO": "C1", "CIUDAD": "BOG", "CUP": "914400", "EXAMEN": None, "INTRA O EXTRA": "Intra", "VALOR": "1000"}])

    result, novelties = validator.validate(df, "TarifasEspeciales")

    assert result["CUP"][0] == "914400"
    assert result["VERIFIED"][0] is True
    assert novelties[0].estado == ESTADO_NO_CORREGIDO


def test_validate_novelties_include_contract_examples():
    validator = CupColumnValidator(FakeCupRepo(_catalog()))
    df = _df([
        {"CONTRATO": "A", "CIUDAD": "BOG", "CUP": "10042", "EXAMEN": "PROTECCION AUDITIVA", "INTRA O EXTRA": "Intra", "VALOR": "1"},
        {"CONTRATO": "B", "CIUDAD": "BOG", "CUP": "10042", "EXAMEN": "PROTECCION AUDITIVA", "INTRA O EXTRA": "Intra", "VALOR": "2"},
    ])

    _, novelties = validator.validate(df, "Paquetes")

    assert set(novelties[0].contratos) <= {"A", "B"}
    assert len(novelties[0].contratos) >= 1
