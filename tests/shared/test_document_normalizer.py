from src.shared.utils.document_normalizer import (
    CEDULA,
    NIT,
    calculate_dian_dv,
    classify_document,
    clean_digits,
    normalize_document,
)


def test_clean_digits_removes_punctuation():
    assert clean_digits("900.111.111-1") == "9001111111"


def test_clean_digits_handles_empty():
    assert clean_digits("") == ""
    assert clean_digits(None) == ""


def test_clasifica_nit_9_digitos_prefijo_8_o_9():
    assert classify_document("900111111") == NIT
    assert classify_document("830029102") == NIT


def test_clasifica_cedula_corta_con_prefijo_8_no_es_nit():
    # 8125007: cédula real de 7 dígitos con prefijo 8 (TABORDA AGUDELO ANDRES FELIPE)
    assert classify_document("8125007") == CEDULA


def test_clasifica_nit_10_digitos_prefijo_8_o_9_con_dv():
    assert classify_document("9001111110") == NIT


def test_clasifica_cedula_10_digitos_prefijo_1():
    assert classify_document("1000017310") == CEDULA


def test_dv_dian_conocido():
    assert calculate_dian_dv("900111111") == 0
    assert calculate_dian_dv("830029102") == 0
    assert calculate_dian_dv("444444444") == 3


def test_nit_9_digitos_se_conserva_igual():
    result = normalize_document("900111111")
    assert result.value == "900111111"
    assert result.kind == NIT
    assert result.truncated is False
    assert result.dv_valid is None


def test_nit_con_puntos_y_guiones_se_limpia_y_acota_a_9():
    result = normalize_document("900.111.111-1")
    assert result.value == "900111111"
    assert result.kind == NIT


def test_nit_10_digitos_dv_valido_se_acota_sin_advertencia():
    result = normalize_document("9001111110")
    assert result.value == "900111111"
    assert result.truncated is True
    assert result.dv_valid is True


def test_nit_10_digitos_dv_invalido_se_acota_con_advertencia():
    result = normalize_document("9001111115")
    assert result.value == "900111111"
    assert result.truncated is True
    assert result.dv_valid is False


def test_cedula_10_digitos_prefijo_1_se_conserva_integra():
    result = normalize_document("1000017310")
    assert result.value == "1000017310"
    assert result.kind == CEDULA
    assert result.truncated is False


def test_cedula_corta_con_prefijo_8_se_conserva_integra():
    result = normalize_document("8125007")
    assert result.value == "8125007"
    assert result.kind == CEDULA
    assert result.truncated is False


def test_cedula_8_digitos_se_conserva_integra():
    result = normalize_document("19146113")
    assert result.value == "19146113"
    assert result.kind == CEDULA


def test_normalize_document_documento_vacio():
    result = normalize_document("")
    assert result.value == ""
    assert result.kind == CEDULA
    assert result.truncated is False
