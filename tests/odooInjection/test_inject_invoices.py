from pathlib import Path

import pytest

from src.odooInjection.application.use_cases.inject_invoices_to_odoo import (
    InjectInvoicesToOdoo,
)
from src.odooInjection.domain.services.city_account_resolver import CityAccountResolver
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_log_generator import FakeLogGenerator
from tests.fakes.fake_odoo_repo import FakeOdooRepo
from tests.fakes.fake_pre_invoice_reader import FakePreInvoiceReader
from tests.fakes.fake_progress import FakeProgress


@pytest.fixture
def config():
    return {
        "url": "https://test.odoo.com",
        "diario_id": 47,
        "cuenta_ingresos_excluidos": 42653,
        "cuenta_ingresos_gravados": 42650,
        "cuenta_receivable": 40921,
        "cuenta_payable": 41977,
        "productos_gravados": ["100006"],
        "taxes": ["TAX1"],
        "nombre_uom": "Unidades",
        "fecha_servicio": "2026-04-30",
        "fecha_vencimiento_dias": 30,
    }


@pytest.fixture
def sample_filas():
    return [
        {
            "NIT": "900111111",
            "Empresa": "EMPRESA A",
            "Ciudad": "BOGOTA",
            "Fecha Ingreso": "2026-04-15",
            "890201": 1,
            "890301": None,
        },
        {
            "NIT": "900111111",
            "Empresa": "EMPRESA A",
            "Ciudad": "MEDELLIN",
            "Fecha Ingreso": "2026-04-16",
            "890201": 1,
            "890301": 1,
        },
    ]


@pytest.fixture
def products():
    return {
        "890201": {"id": 1, "name": "HEMOGRAMA", "default_code": "890201", "list_price": 15000},
        "890301": {"id": 2, "name": "GLUCOSA", "default_code": "890301", "list_price": 12000},
    }


def test_inject_creates_invoice(config, sample_filas, products, tmp_path):
    odoo_repo = FakeOdooRepo(
        products=products,
        clients={"900111111": {"id": 1, "name": "EMPRESA A"}},
    )
    reader = FakePreInvoiceReader(filas=sample_filas, cols_examenes=["890201", "890301"])
    log_gen = FakeLogGenerator()

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=log_gen,
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert len(resultados) == 1
    assert resultados[0].estado == "OK"
    assert resultados[0].nit == "900111111"
    assert len(odoo_repo._created_invoices) == 1

    invoice = odoo_repo._created_invoices[0]
    assert invoice["partner_id"] == 1
    assert invoice["move_type"] == "out_invoice"
    assert len(invoice["invoice_line_ids"]) > 0


def test_inject_creates_client_when_not_found(config, sample_filas, products, tmp_path):
    odoo_repo = FakeOdooRepo(products=products, clients={})
    reader = FakePreInvoiceReader(filas=sample_filas, cols_examenes=["890201", "890301"])

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=FakeLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert resultados[0].estado == "OK"
    assert "900111111" in odoo_repo._clients


def test_inject_returns_error_when_no_products(config, tmp_path):
    filas = [{"NIT": "900111111", "Empresa": "X", "Ciudad": "BOGOTA", "Fecha Ingreso": "2026-04-15", "999999": 1}]
    odoo_repo = FakeOdooRepo(products={}, clients={"900111111": {"id": 1, "name": "X"}})
    reader = FakePreInvoiceReader(filas=filas, cols_examenes=["999999"])

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=FakeLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert resultados[0].estado == "ERROR"
    assert "Sin líneas válidas" in resultados[0].detalle


def test_inject_returns_verificar_for_invalid_nit(config, tmp_path):
    filas = [{"NIT": "123", "Empresa": "X", "Ciudad": "BOGOTA", "Fecha Ingreso": "2026-04-15", "890201": 1}]
    products = {"890201": {"id": 1, "name": "HEMO", "default_code": "890201", "list_price": 10000}}
    odoo_repo = FakeOdooRepo(products=products, clients={})
    reader = FakePreInvoiceReader(filas=filas, cols_examenes=["890201"])

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=FakeLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert resultados[0].estado == "VERIFICAR"
    assert "NIT inválido" in resultados[0].detalle


def test_inject_empty_input(config, tmp_path):
    odoo_repo = FakeOdooRepo()
    reader = FakePreInvoiceReader(filas=[], cols_examenes=[])

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=FakeLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert resultados == []


def test_inject_groups_by_city_and_product(config, products, tmp_path):
    filas = [
        {"NIT": "900111111", "Empresa": "A", "Ciudad": "BOGOTA", "Fecha Ingreso": "2026-04-15", "890201": 1},
        {"NIT": "900111111", "Empresa": "A", "Ciudad": "BOGOTA", "Fecha Ingreso": "2026-04-15", "890201": 1},
        {"NIT": "900111111", "Empresa": "A", "Ciudad": "MEDELLIN", "Fecha Ingreso": "2026-04-15", "890201": 1},
    ]
    odoo_repo = FakeOdooRepo(products=products, clients={"900111111": {"id": 1, "name": "A"}})
    reader = FakePreInvoiceReader(filas=filas, cols_examenes=["890201"])

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=reader,
        city_resolver=CityAccountResolver(),
        log_generator=FakeLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
        config=config,
    )

    resultados = use_case.execute(Path("input"), tmp_path)

    assert resultados[0].estado == "OK"
    invoice = odoo_repo._created_invoices[0]
    # 2 líneas: (890201, BOGOTA) x2 y (890201, MEDELLIN) x1
    assert len(invoice["invoice_line_ids"]) == 2
