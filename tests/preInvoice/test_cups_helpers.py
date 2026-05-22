"""Tests para helpers de CUPS en SplitByNit."""
from src.preInvoice.application.use_cases.split_by_nit import SplitByNit
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_logger import FakeLogger


def test_is_cups_column_digits():
    assert SplitByNit._is_cups_column("100004") is True


def test_is_cups_column_with_dash():
    assert SplitByNit._is_cups_column("860205-1") is True


def test_is_cups_column_text():
    assert SplitByNit._is_cups_column("NIT") is False
    assert SplitByNit._is_cups_column("Total") is False


def test_is_cups_column_none():
    assert SplitByNit._is_cups_column(None) is False


def test_is_cups_column_empty():
    assert SplitByNit._is_cups_column("") is False


def test_get_active_cups_indices_empty():
    rows = [[None, None], [None, None]]
    assert SplitByNit._get_active_cups_indices(rows, [0, 1]) == []


def test_get_active_cups_indices_with_value():
    rows = [["x", None, 5000], ["y", None, None]]
    assert SplitByNit._get_active_cups_indices(rows, [1, 2]) == [2]


def test_build_cups_name_map_found():
    from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
    import logging
    logger = LoggerAdapter("test")
    logger._logger.setLevel(logging.DEBUG)
    repo = FakeCupRepo([{"id": 1, "code": "100004", "name": "PERFIL"}])
    sbn = SplitByNit(logger, repo)
    assert sbn._build_cups_name_map(["100004"]) == {"100004": "PERFIL"}


def test_build_cups_name_map_no_repo():
    from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
    logger = LoggerAdapter("test")
    sbn = SplitByNit(logger, None)
    assert sbn._build_cups_name_map(["100004"]) == {}
