"""Tests unitarios para _enrich_with_invoices."""
import polars as pl
import pytest

from src.assign.application.use_cases.assigned_rates import _enrich_with_invoices


class _FakeLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, msg, **_):
        self.warnings.append(msg)

    def info(self, msg, **_):
        self.infos.append(msg)


def _df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={k: pl.Utf8 for k in rows[0]})


def _facture(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={"N° Identificación": pl.Utf8, "# FACTURA": pl.Utf8})


# ── Casos base ────────────────────────────────────────────────────────

def test_coincidencia_exacta():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([{"N° Identificación": "123", "# FACTURA": "SET001"}])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


def test_sin_match_retorna_cadena_vacia():
    df = _df([{"N° Identificación": "999", "Nombre": "B"}])
    df_f = _facture([{"N° Identificación": "123", "# FACTURA": "SET001"}])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == ""


def test_multiples_facturas_concatenadas():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([
        {"N° Identificación": "123", "# FACTURA": "SET001"},
        {"N° Identificación": "123", "# FACTURA": "SET002"},
    ])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    facturas = set(result["FACTURAS"][0].split(", "))
    assert facturas == {"SET001", "SET002"}


def test_filtra_facturas_sin_prefijo_set():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([
        {"N° Identificación": "123", "# FACTURA": "SET001"},
        {"N° Identificación": "123", "# FACTURA": "FAC999"},
    ])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


def test_sin_facturas_set_retorna_vacio():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([{"N° Identificación": "123", "# FACTURA": "FAC001"}])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == ""


def test_normalizacion_mayusculas_y_espacios():
    df = _df([{"N° Identificación": " 123 ", "Nombre": "A"}])
    df_f = _facture([{"N° Identificación": "123", "# FACTURA": "SET001"}])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


def test_deduplicacion_facturas_repetidas():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([
        {"N° Identificación": "123", "# FACTURA": "SET001"},
        {"N° Identificación": "123", "# FACTURA": "SET001"},
    ])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


def test_warning_cuando_multiples_facturas():
    df = _df([{"N° Identificación": "123", "Nombre": "A"}])
    df_f = _facture([
        {"N° Identificación": "123", "# FACTURA": "SET001"},
        {"N° Identificación": "123", "# FACTURA": "SET002"},
    ])
    logger = _FakeLogger()
    _enrich_with_invoices(df, df_f, logger)
    assert any("más de una factura" in w for w in logger.warnings)


def test_multiples_filas_en_df():
    df = _df([
        {"N° Identificación": "111", "Nombre": "A"},
        {"N° Identificación": "222", "Nombre": "B"},
        {"N° Identificación": "333", "Nombre": "C"},
    ])
    df_f = _facture([
        {"N° Identificación": "111", "# FACTURA": "SET010"},
        {"N° Identificación": "333", "# FACTURA": "SET030"},
    ])
    result = _enrich_with_invoices(df, df_f, _FakeLogger())
    facturas = dict(zip(result["N° Identificación"].to_list(), result["FACTURAS"].to_list()))
    assert facturas["111"] == "SET010"
    assert facturas["222"] == ""
    assert facturas["333"] == "SET030"
