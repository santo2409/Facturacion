"""Tests para la generación de la columna Total (suma de columnas CUP)."""
import polars as pl


def compute_total(df: pl.DataFrame, cup_headers: list[str]) -> pl.DataFrame:
    """Calcula la columna Total como suma horizontal de columnas CUP."""
    if not cup_headers:
        return df.with_columns(pl.lit(0).alias("Total"))
    return df.with_columns(
        pl.sum_horizontal([pl.col(h) for h in cup_headers]).alias("Total")
    )


def is_integer_parseable(x):
    return str(x).replace("-", "").isdigit()


def test_total_suma_columnas_cup():
    """Columnas CUP numéricas → Total es la suma horizontal."""
    df = pl.DataFrame({
        "NIT": ["900111111", "900222222"],
        "Empresa": ["A", "B"],
        "890201": [5000, 3000],
        "890301": [2000, 1000],
    })
    headers = [c for c in df.columns if is_integer_parseable(c)]
    result = compute_total(df, headers)
    assert result["Total"].to_list() == [7000, 4000]


def test_total_con_valores_uno():
    """Columnas CUP con valor 1 (sin tarificar) → se suman como están."""
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "890201": [1],
        "890301": [1],
        "890401": [5000],
    })
    headers = [c for c in df.columns if is_integer_parseable(c)]
    result = compute_total(df, headers)
    assert result["Total"].to_list() == [5002]


def test_total_sin_columnas_cup():
    """DataFrame sin columnas CUP → Total es 0."""
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Empresa": ["A"],
    })
    headers = [c for c in df.columns if is_integer_parseable(c)]
    result = compute_total(df, headers)
    assert result["Total"].to_list() == [0]


def test_total_columna_existe_en_resultado():
    """La columna Total debe existir en el DataFrame resultante."""
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "890201": [100],
    })
    headers = [c for c in df.columns if is_integer_parseable(c)]
    result = compute_total(df, headers)
    assert "Total" in result.columns
