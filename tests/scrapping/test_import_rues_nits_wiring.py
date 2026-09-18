"""Tests de la preparación de datos del controller de la opción 1."""
import polars as pl

from src.scrapping.infrastructure.console.import_rues_nits import build_book_names
from tests.fakes.fake_logger import FakeLogger


def test_build_book_names_maps_nit_to_company():
    df = pl.DataFrame({"nits": ["111", "222"], "empresa": ["EMPRESA A", "EMPRESA B"]})

    assert build_book_names(df, FakeLogger()) == {
        "111": "EMPRESA A",
        "222": "EMPRESA B",
    }


def test_build_book_names_skips_empty_company():
    df = pl.DataFrame({"nits": ["111", "222"], "empresa": ["EMPRESA A", None]})

    assert build_book_names(df, FakeLogger()) == {"111": "EMPRESA A"}


def test_warns_user_when_sheet_has_no_empresa_column():
    df = pl.DataFrame({"nits": ["111"]})
    logger = FakeLogger()

    result = build_book_names(df, logger)

    assert result == {}
    assert logger.warnings
