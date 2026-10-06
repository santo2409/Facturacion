"""Tests para DuplicateCompanyDetector, validados contra pares reales medidos
en la BD de producción (8.605 empresas) y contra los falsos positivos
conocidos del enfoque difuso general que se descartó."""
from src.company.domain.services.duplicate_company_detector import (
    REASON_NIT_SUFFIX,
    REASON_SAME_NAME,
    DuplicateCompanyDetector,
)
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger


def _company(nit, name):
    return {"id": 1, "nit": nit, "name": name}


def build(fuzz=None, threshold=85):
    return DuplicateCompanyDetector(fuzz or FakeFuzz(), similarity_threshold=threshold)


def RealFuzzForTests():
    """RapidFuzzBiller real: los tests de la Regla B validan contra el
    puntaje genuino de RapidFuzz, no una simulación."""
    return RapidFuzzBiller(FakeLogger())


# ── Regla A: nombre idéntico ignorando puntuación y espacios ────────────────


def test_regla_a_detecta_nombre_identico_ignorando_puntuacion():
    """Caso real: LAB3 SAS (901545404) vs LAB3 S.A.S (901546404)."""
    detector = build()
    companies = [
        _company("901545404", "LAB3 SAS"),
        _company("901546404", "LAB3 S.A.S"),
    ]

    candidates = detector.detect(companies)

    assert len(candidates) == 1
    c = candidates[0]
    assert {c.nit_a, c.nit_b} == {"901545404", "901546404"}
    assert REASON_SAME_NAME in c.reasons


def test_regla_a_ignora_diferencias_de_espaciado():
    detector = build()
    companies = [
        _company("111", "SEGURIDAD PRIVADA K G B LTDA"),
        _company("222", "SEGURIDAD PRIVADA KGB LTDA"),
    ]

    candidates = detector.detect(companies)

    assert len(candidates) == 1
    assert REASON_SAME_NAME in candidates[0].reasons


def test_regla_a_no_agrupa_mismo_nit():
    detector = build()
    companies = [_company("111", "EMPRESA A"), _company("111", "EMPRESA A")]

    assert detector.detect(companies) == []


def test_regla_a_detecta_grupo_de_tres():
    detector = build()
    companies = [
        _company("111", "EMPRESA A SAS"),
        _company("222", "EMPRESA A S.A.S"),
        _company("333", "EMPRESA A S A S"),
    ]

    candidates = detector.detect(companies)

    pares = {frozenset([c.nit_a, c.nit_b]) for c in candidates}
    assert pares == {
        frozenset(["111", "222"]),
        frozenset(["111", "333"]),
        frozenset(["222", "333"]),
    }


def test_regla_a_no_agrupa_nombres_distintos():
    """AC-04: CENTRO ELDORADO TORRE A vs TORRE B son empresas distintas."""
    detector = build()
    companies = [
        _company("800116542", "CENTRO ELDORADO TORRE A"),
        _company("830077036", "CENTRO ELDORADO TORRE B"),
    ]

    assert detector.detect(companies) == []


def test_detector_handles_empty_company_list():
    assert build().detect([]) == []


def test_detector_ignores_companies_without_name():
    detector = build()
    companies = [_company("111", ""), _company("222", "")]

    assert build().detect(companies) == []


# ── Regla B: NIT + dígito final, con umbral de similitud ────────────────────


def test_regla_b_detecta_nit_con_digito_final_y_similitud_alta():
    """Caso real: 19146113 vs 191461130 (dígito de verificación pegado)."""
    detector = build(fuzz=RealFuzzForTests())
    companies = [
        _company("19146113", "MARIO ALBERTO HUERTAS COTES"),
        _company("191461130", "HUERTAS COTES MARIO ALBERTO"),
    ]

    candidates = detector.detect(companies)

    assert len(candidates) == 1
    c = candidates[0]
    assert {c.nit_a, c.nit_b} == {"19146113", "191461130"}
    assert REASON_NIT_SUFFIX in c.reasons
    assert c.similarity == 100


def test_regla_b_descarta_coincidencia_fortuita_de_prefijo_bajo_umbral():
    """AC-03: 830029102 vs 8300291028 son empresas distintas (similitud 29)."""
    detector = build(fuzz=RealFuzzForTests())
    companies = [
        _company("830029102", "SALUD OCUPACIONAL DE LOS ANDES LIMITADA"),
        _company("8300291028", "FRANCY GISSEL LOPEZ CARO"),
    ]

    assert detector.detect(companies) == []


def test_regla_b_descarta_nit_generico_sin_similitud():
    """AC-04: 444444444 vs 4444444444 son empresas distintas (similitud 25)."""
    detector = build(fuzz=RealFuzzForTests())
    companies = [
        _company("444444444", "ENTIDADES O SOCIEDADES EN EL EXTERIOR"),
        _company("4444444444", "ACMI MEXICO"),
    ]

    assert detector.detect(companies) == []


def test_regla_b_no_aplica_sin_nit_base_registrado():
    detector = build(fuzz=RealFuzzForTests())
    companies = [_company("1234567890", "EMPRESA SOLA")]

    assert detector.detect(companies) == []


# ── Deduplicación: un par detectado por ambas reglas ─────────────────────────


def test_par_detectado_por_ambas_reglas_aparece_una_sola_vez():
    """Caso real: 83004087 (COBRA S.A) vs 830040872 (COBRA S A) — cumple
    la Regla A (nombre idéntico sin puntuación) y la Regla B (dígito final +
    similitud 97)."""
    detector = build(fuzz=RealFuzzForTests())
    companies = [
        _company("83004087", "ACTIVIDADES DE INSTALACIONES Y SERVICIOS COBRA S.A"),
        _company("830040872", "ACTIVIDADES DE INSTALACIONES Y SERVICIOS COBRA S A"),
    ]

    candidates = detector.detect(companies)

    assert len(candidates) == 1
    c = candidates[0]
    assert {c.nit_a, c.nit_b} == {"83004087", "830040872"}
    assert REASON_SAME_NAME in c.reasons
    assert REASON_NIT_SUFFIX in c.reasons
    assert c.similarity > 0


def test_candidates_have_stable_nit_order():
    detector = build()
    companies = [
        _company("222", "EMPRESA A"),
        _company("111", "EMPRESA A"),
    ]

    c = detector.detect(companies)[0]

    assert c.nit_a == "111"
    assert c.nit_b == "222"
