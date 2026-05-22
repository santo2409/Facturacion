"""Tests para la generación de la columna Total."""
import polars as pl


def compute_total(df: pl.DataFrame, cup_headers: list[str]) -> pl.DataFrame:
    if not cup_headers:
        return df.with_columns(pl.lit(0).alias("Total"))
    return df.with_columns(
        pl.sum_horizontal([pl.col(h) for h in cup_headers]).alias("Total")
    )


def test_total_suma_columnas_cup():
    df = pl.DataFrame({"NIT": ["A", "B"], "890201": [5000, 3000], "890301": [2000, 1000]})
    headers = [c for c in df.columns if c.replace("-", "").isdigit()]
    result = compute_total(df, headers)
    assert result["Total"].to_list() == [7000, 4000]


def test_total_sin_columnas_cup():
    df = pl.DataFrame({"NIT": ["A"], "Empresa": ["X"]})
    headers = [c for c in df.columns if c.replace("-", "").isdigit()]
    result = compute_total(df, headers)
    assert result["Total"].to_list() == [0]


def test_total_columna_existe():
    df = pl.DataFrame({"NIT": ["A"], "890201": [100]})
    headers = [c for c in df.columns if c.replace("-", "").isdigit()]
    result = compute_total(df, headers)
    assert "Total" in result.columns
