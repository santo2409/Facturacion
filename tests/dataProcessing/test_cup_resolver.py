"""Tests para CupResolver: la cascada F1 -> F2 -> F3 -> F4 de corrección de CUPs.

Ver specs/005_correccion-cups-por-nombre/plan.md sección 3.3.
"""
from src.dataProcessing.domain.entities.cup_novelty import (
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_HOMOLOGADO_BASE,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
    ESTADO_NO_CORREGIDO,
    FASE_NOMBRE,
    FASE_COOCURRENCIA,
    FASE_SUFIJO,
    FASE_SUGERENCIA,
)
from src.dataProcessing.domain.services.cup_resolver import CupResolver
from tests.fakes.fake_fuzz import FakeFuzz


def _catalog():
    return [
        {"id": 1, "code": "100042", "name": "PROTECCION AUDITIVA"},
        {"id": 2, "code": "903868", "name": "TRIGLICERIDOS"},
        {"id": 3, "code": "907002", "name": "Coprológico"},
        {"id": 4, "code": "904704", "name": "INSULINA (CADA MUESTRA)"},
        {"id": 5, "code": "954107-01", "name": "AUDIOMETRIA CONFIRMATORIA"},
        {"id": 6, "code": "954107", "name": "AUDIOMETRÍA DE TONOS PUROS"},
    ]


# ---- T03: F1, nombre exacto ----------------------------------------------

def test_resolve_valid_cup_returns_no_novelty():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("903868", "TRIGLICERIDOS", coocurrence={})
    assert result.cup == "903868"
    assert result.corregido is False
    assert result.estado is None


def test_resolve_exact_name_match_corrects_cup_protection_auditiva():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("10042", "PROTECCION AUDITIVA", coocurrence={})
    assert result.cup == "100042"
    assert result.corregido is True
    assert result.estado == ESTADO_CORREGIDO_NOMBRE
    assert result.fase == FASE_NOMBRE


def test_resolve_exact_name_match_corrects_cup_trigliceridos():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("903717", "TRIGLICERIDOS", coocurrence={})
    assert result.cup == "903868"
    assert result.estado == ESTADO_CORREGIDO_NOMBRE


def test_resolve_exact_name_match_tolerates_accents_and_case():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("99999", "COPROLOGICO", coocurrence={})
    assert result.cup == "907002"


def test_resolve_no_correction_when_no_exact_name_and_no_other_phase():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("3", "UN EXAMEN QUE NO EXISTE", coocurrence={})
    assert result.cup == "3"
    assert result.corregido is False
    assert result.estado == ESTADO_NO_CORREGIDO


def test_resolve_colliding_catalog_names_excluded_from_index():
    catalog = _catalog() + [{"id": 7, "code": "999001", "name": "TRIGLICERIDOS"}]
    resolver = CupResolver(catalog)
    result = resolver.resolve("1", "TRIGLICERIDOS", coocurrence={})
    # "TRIGLICERIDOS" now maps to two different codes -> ambiguous, excluded
    assert result.corregido is False
    assert result.estado == ESTADO_NO_CORREGIDO


# ---- T04: F2, co-ocurrencia -----------------------------------------------

def test_resolve_coocurrence_single_candidate_corrects_cup():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("8", "GLICEMIA", coocurrence={"GLICEMIA": ["903841"]})
    assert result.cup == "903841"
    assert result.corregido is True
    assert result.estado == ESTADO_CORREGIDO_COOCURRENCIA
    assert result.fase == FASE_COOCURRENCIA


def test_resolve_coocurrence_ambiguous_does_not_correct():
    resolver = CupResolver(_catalog())
    result = resolver.resolve(
        "3", "OPTOMETRIA", coocurrence={"OPTOMETRIA": ["890207", "890262-01"]}
    )
    assert result.cup == "3"
    assert result.corregido is False
    assert result.estado == ESTADO_NO_CORREGIDO
    assert "890207" in result.detalle and "890262-01" in result.detalle


def test_resolve_name_match_takes_priority_over_coocurrence():
    resolver = CupResolver(_catalog())
    # "PROTECCION AUDITIVA" resolves via F1 to 100042; coocurrence disagrees on purpose
    result = resolver.resolve(
        "10042", "PROTECCION AUDITIVA", coocurrence={"PROTECCION AUDITIVA": ["999999"]}
    )
    assert result.cup == "100042"
    assert result.fase == FASE_NOMBRE


# ---- T05: F3, homologación de sufijo --------------------------------------

def test_resolve_suffix_homologation_corrects_to_base_cup():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("904704-1", None, coocurrence={})
    assert result.cup == "904704"
    assert result.corregido is True
    assert result.estado == ESTADO_HOMOLOGADO_BASE
    assert result.fase == FASE_SUFIJO


def test_resolve_suffix_homologation_does_not_invent_missing_base():
    resolver = CupResolver(_catalog())
    result = resolver.resolve("91217-99", None, coocurrence={})
    assert result.cup == "91217-99"
    assert result.corregido is False
    assert result.estado == ESTADO_NO_CORREGIDO


def test_resolve_suffix_tried_only_after_name_and_coocurrence():
    # base "954107" exists, but exact-name match to "954107-01" must win first
    resolver = CupResolver(_catalog())
    result = resolver.resolve("954107-0", "AUDIOMETRIA CONFIRMATORIA", coocurrence={})
    assert result.cup == "954107-01"
    assert result.fase == FASE_NOMBRE


# ---- T06: F4, sugerencia difusa (nunca aplicada) ---------------------------

def test_resolve_fuzzy_suggestion_never_writes_cup():
    fuzz = FakeFuzz(override={"BENCENOTOLUENOXILENO": "COMPLEJO BTX"})
    catalog = _catalog() + [{"id": 8, "code": "208100", "name": "COMPLEJO BTX"}]
    resolver = CupResolver(catalog, fuzz=fuzz, threshold=90)
    result = resolver.resolve("901500-01", "BENCENOTOLUENOXILENO", coocurrence={})
    assert result.cup == "901500-01"
    assert result.corregido is False
    assert result.estado == ESTADO_NO_CORREGIDO_SUGERENCIA
    assert result.fase == FASE_SUGERENCIA
    assert "208100" in result.detalle


def test_resolve_without_fuzz_falls_back_to_no_corregido():
    resolver = CupResolver(_catalog(), fuzz=None)
    result = resolver.resolve("901500-01", "ALGO SIN MATCH", coocurrence={})
    assert result.cup == "901500-01"
    assert result.estado == ESTADO_NO_CORREGIDO


def test_resolve_fuzzy_only_evaluated_when_deterministic_phases_fail():
    fuzz = FakeFuzz()
    resolver = CupResolver(_catalog(), fuzz=fuzz)
    result = resolver.resolve("10042", "PROTECCION AUDITIVA", coocurrence={})
    assert result.fase == FASE_NOMBRE  # never reaches F4


# ---- is_valid ---------------------------------------------------------

def test_is_valid_true_for_catalog_code():
    resolver = CupResolver(_catalog())
    assert resolver.is_valid("903868") is True


def test_is_valid_false_for_unknown_code():
    resolver = CupResolver(_catalog())
    assert resolver.is_valid("10042") is False
