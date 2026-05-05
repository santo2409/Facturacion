"""Tests para helpers de identificación CUPS y construcción de mapa de nombres."""
import logging

import pytest

from src.preInvoice.application.use_cases.split_by_nit import SplitByNit
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


@pytest.fixture
def logger():
    adapter = LoggerAdapter("test_cups_helpers")
    adapter._logger.setLevel(logging.DEBUG)
    return adapter


class FakeCupRepo:
    def __init__(self, data):
        self._data = data

    def exists(self, cup):
        return any(c["code"] == cup for c in self._data)

    def get_all_cups(self):
        return [c["code"] for c in self._data]

    def get_all(self):
        return self._data


# ── is_cups_column ──────────────────────────────────────────────────────

def test_is_cups_column_digits_only():
    assert SplitByNit._is_cups_column("100004") is True


def test_is_cups_column_with_dash():
    assert SplitByNit._is_cups_column("860205-1") is True


def test_is_cups_column_with_leading_zero():
    assert SplitByNit._is_cups_column("860205-01") is True


def test_is_cups_column_fixed_names():
    for name in ["NIT", "Total", "Empresa", "Base", "FACTURADOR"]:
        assert SplitByNit._is_cups_column(name) is False


def test_is_cups_column_none():
    assert SplitByNit._is_cups_column(None) is False


def test_is_cups_column_empty():
    assert SplitByNit._is_cups_column("") is False


# ── build_cups_name_map ─────────────────────────────────────────────────

def test_build_cups_name_map_found(logger):
    repo = FakeCupRepo([{"id": 1, "code": "100004", "name": "PERFIL LIPÍDICO"}])
    sbn = SplitByNit(logger, repo)
    result = sbn._build_cups_name_map(["100004"])
    assert result == {"100004": "PERFIL LIPÍDICO"}


def test_build_cups_name_map_not_found(logger, caplog):
    repo = FakeCupRepo([])
    sbn = SplitByNit(logger, repo)
    with caplog.at_level(logging.WARNING):
        result = sbn._build_cups_name_map(["999999"])
    assert result == {"999999": ""}
    assert "999999" in caplog.text


def test_build_cups_name_map_no_repo(logger):
    sbn = SplitByNit(logger, None)
    assert sbn._build_cups_name_map(["100004"]) == {}


# ── get_active_cups_indices ─────────────────────────────────────────────

def test_empty_cups_columns_removed():
    rows = [[None, None, None], [None, None, None]]
    assert SplitByNit._get_active_cups_indices(rows, [1, 2]) == []


def test_cups_with_whitespace_only_removed():
    rows = [["x", "  ", ""], ["y", "   ", None]]
    assert SplitByNit._get_active_cups_indices(rows, [1, 2]) == []


def test_cups_with_at_least_one_value_kept():
    rows = [["x", None, 5000], ["y", None, None]]
    assert SplitByNit._get_active_cups_indices(rows, [1, 2]) == [2]


def test_all_cups_empty_returns_empty():
    rows = [["x", None, None]]
    assert SplitByNit._get_active_cups_indices(rows, [1, 2]) == []
