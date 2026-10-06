from src.shared.utils.text_normalizer import (
    normalize_name,
    normalize_name_hash,
    normalize_nit,
    normalize_upper_spaces,
    pl_normalize_name,
    pl_normalize_upper,
)

import polars as pl


def test_normalize_name_basic():
    assert normalize_name("  café & Ñoño S.A.S  ") == "CAF & ÑOÑO SAS"


def test_normalize_name_keeps_ampersand_and_enie():
    assert normalize_name("A&B Ñ") == "A&B Ñ"


def test_normalize_name_collapses_spaces():
    assert normalize_name("  HELLO   WORLD  ") == "HELLO WORLD"


def test_normalize_name_empty():
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def test_normalize_name_hash():
    assert normalize_name_hash("CARGO #1 - test!") == "CARGO #1 TEST"


def test_normalize_nit():
    assert normalize_nit("900.123.456-7") == "900123456"
    assert normalize_nit("12345") == "12345"
    assert normalize_nit("") == ""
    assert normalize_nit(None) == ""


def test_normalize_nit_long_number():
    assert normalize_nit("9001234567890") == "900123456"


def test_normalize_upper_spaces():
    assert normalize_upper_spaces("  hello   world  ") == "HELLO WORLD"


def test_normalize_upper_spaces_empty():
    assert normalize_upper_spaces("") == ""
    assert normalize_upper_spaces(None) == ""


def test_pl_normalize_name():
    df = pl.DataFrame({"col": ["  café & Ñoño S.A.S  ", "  HELLO   WORLD  "]})
    result = df.select(pl_normalize_name("col").alias("col"))
    assert result["col"][0] == "CAF & ÑOÑO SAS"
    assert result["col"][1] == "HELLO WORLD"


def test_pl_normalize_upper():
    df = pl.DataFrame({"col": ["  hello   world  ", "  Test  "]})
    result = df.select(pl_normalize_upper("col").alias("col"))
    assert result["col"][0] == "HELLO WORLD"
    assert result["col"][1] == "TEST"


def test_normalize_text_key_transliterates_and_collapses():
    from src.shared.utils.text_normalizer import normalize_text_key

    assert normalize_text_key("  Coprológico  ") == "COPROLOGICO"
    assert normalize_text_key("TRIGLICÉRIDOS") == "TRIGLICERIDOS"
    assert normalize_text_key("") == ""
    assert normalize_text_key(None) == ""


def test_normalize_company_name_delegates_to_normalize_text_key():
    from src.shared.utils.text_normalizer import normalize_company_name, normalize_text_key

    assert normalize_company_name("Clínica SAS") == normalize_text_key("Clínica SAS")
