"""Tests para ExcelLogGenerator.

Regresión: generate() sobrescribía log_inyeccion.xlsx completo en cada corrida
en vez de fusionarlo con el histórico, por lo que empresas ya facturadas en
corridas anteriores desaparecían del log y quedaban expuestas a re-inyección
duplicada en Odoo.
"""
from src.odooInjection.domain.entities.invoice_result import InvoiceResult
from src.odooInjection.infrastructure.reporting.excel_log_generator import (
    ExcelLogGenerator,
)
from tests.fakes.fake_logger import FakeLogger


def test_generate_accumulates_results_across_runs(tmp_path):
    gen = ExcelLogGenerator(FakeLogger())

    gen.generate([InvoiceResult("900111111", "EMPRESA A", "OK", "Factura 1")], tmp_path)
    gen.generate([InvoiceResult("900222222", "EMPRESA B", "OK", "Factura 2")], tmp_path)

    log_path = tmp_path / "log_inyeccion.xlsx"
    assert gen.read_successful_nits(log_path) == {"900111111", "900222222"}


def test_generate_replaces_only_the_reprocessed_nit(tmp_path):
    gen = ExcelLogGenerator(FakeLogger())

    gen.generate([InvoiceResult("900111111", "EMPRESA A", "ERROR", "fallo inicial")], tmp_path)
    gen.generate([InvoiceResult("900111111", "EMPRESA A", "OK", "Factura 1")], tmp_path)

    log_path = tmp_path / "log_inyeccion.xlsx"
    assert gen.read_successful_nits(log_path) == {"900111111"}


def test_read_successful_nits_warns_instead_of_silently_returning_empty(tmp_path):
    log_path = tmp_path / "log_inyeccion.xlsx"
    log_path.write_bytes(b"esto no es un archivo xlsx valido")
    logger = FakeLogger()
    gen = ExcelLogGenerator(logger)

    result = gen.read_successful_nits(log_path)

    assert result == set()
    assert logger.warnings
