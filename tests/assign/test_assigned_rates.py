"""Tests para AssignRatesFromExcel use case."""
import json
import os

import polars as pl
import pytest

from src.assign.application.use_cases.assigned_rates import AssignRatesFromExcel, _enrich_with_invoices
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo
from tests.fakes.fake_city_repo import FakeCityRepo
from tests.fakes.fake_activity_repo import FakeActivityRepo
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_odoo_repo import FakeOdooRepo
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_odoo_repo import FakeOdooRepo
from src.scrapping.domain.entities.nit_result import NitResult


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    # Create data.json
    data = [{"nit": "900111111", "name": "EMPRESA A"}]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)

    biller_repo = FakeBillerRepo([{"id": 1, "name": "ALFA"}])
    company_repo = FakeCompanyRepo([{"id": 1, "nit": "900111111", "name": "EMPRESA A"}])
    biller_company_repo = FakeBillerCompanyRepo()
    biller_company_repo._data = [{"company": 1, "biller": 1}]
    company_repo._packages = [{"company": 1, "package": 1, "model": "Package"}]

    return {
        "biller_repo": biller_repo,
        "company_repo": company_repo,
        "biller_company_repo": biller_company_repo,
        "package_repo": FakePackageRepo([{"id": 1, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([{"id": 2, "name": "PROVEEDOR X"}]),
        "special_repo": FakeSpecialRepo([{"id": 3, "name": "ESPECIAL A"}]),
        "city_repo": FakeCityRepo([{"id": 1, "name": "BOGOTA"}]),
        "activities_repo": FakeActivityRepo(),
        "rates_repo": FakeRatesRepo(),
        "cup_repo": FakeCupRepo([{"id": 1, "code": "890201", "name": "HEMOGRAMA"}]),
        "nit_service": FakeNitService(),
        "fuzz": FakeFuzz(),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
    }


def _build(deps):
    return AssignRatesFromExcel(**deps)


# ── Tests para _enrich_with_invoices ──────────────────────────────────

def test_enrich_exact_match():
    df = pl.DataFrame({"N° Identificación": ["123"], "Nombre": ["A"]})
    df_f = pl.DataFrame({"N° Identificación": ["123"], "# FACTURA": ["SET001"]})
    result = _enrich_with_invoices(df, df_f, FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


def test_enrich_no_match():
    df = pl.DataFrame({"N° Identificación": ["999"], "Nombre": ["B"]})
    df_f = pl.DataFrame({"N° Identificación": ["123"], "# FACTURA": ["SET001"]})
    result = _enrich_with_invoices(df, df_f, FakeLogger())
    assert result["FACTURAS"][0] == ""


def test_enrich_includes_non_set():
    df = pl.DataFrame({"N° Identificación": ["123"], "Nombre": ["A"]})
    df_f = pl.DataFrame({"N° Identificación": ["123", "123"], "# FACTURA": ["SET001", "FAC999"]})
    result = _enrich_with_invoices(df, df_f, FakeLogger())
    facturas = set(result["FACTURAS"][0].split(", "))
    assert facturas == {"SET001", "FAC999"}


def test_enrich_multiple_facturas():
    df = pl.DataFrame({"N° Identificación": ["123"], "Nombre": ["A"]})
    df_f = pl.DataFrame({"N° Identificación": ["123", "123"], "# FACTURA": ["SET001", "SET002"]})
    result = _enrich_with_invoices(df, df_f, FakeLogger())
    facturas = set(result["FACTURAS"][0].split(", "))
    assert facturas == {"SET001", "SET002"}


def test_enrich_deduplicates():
    df = pl.DataFrame({"N° Identificación": ["123"], "Nombre": ["A"]})
    df_f = pl.DataFrame({"N° Identificación": ["123", "123"], "# FACTURA": ["SET001", "SET001"]})
    result = _enrich_with_invoices(df, df_f, FakeLogger())
    assert result["FACTURAS"][0] == "SET001"


# ── Tests para métodos internos de AssignRatesFromExcel ───────────────

def test_normalize_nit(deps):
    uc = _build(deps)
    df = pl.DataFrame({"NIT": ["900111111", "12345"], "Empresa": ["A", "B"],
                       "Base": ["X", "Y"]})
    result = uc._normalize_nit(df)
    assert result["NIT"][0] == "900111111"
    assert result["NIT"][1] == "12345"


def test_normalize_nit_with_dots(deps):
    uc = _build(deps)
    # extract_all(\d+).list.first() gets first consecutive digit group
    df = pl.DataFrame({"NIT": ["900111111-7"], "Empresa": ["A"], "Base": ["X"]})
    result = uc._normalize_nit(df)
    assert result["NIT"][0] == "900111111"


def test_build_lookups(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert "900111111" in lookups["nit_to_company"]
    assert 1 in lookups["company_to_biller"]
    assert "BOGOTA" in lookups["city_name_to_id"]
    assert "890201" in lookups["cup_code_to_id"]


def test_assign_facturador(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900111111", "999999999"]})
    result = uc._assign_facturador(df, lookups)
    assert result["FACTURADOR"][0] == "ALFA"
    assert result["FACTURADOR"][1] == "GENERAL"
    assert result["Especial / General"][0] == "ESPECIAL"
    assert result["Especial / General"][1] == "GENERAL"


def test_assign_paquete(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900111111"]})
    result = uc._assign_paquete(df, lookups)
    assert result["PAQUETE"][0] == "PAQUETE BASICO"


def test_assign_rates_replaces_1_with_price(deps):
    # Pre-populate rates cache
    deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    result = uc._assign_rates(df, lookups)
    assert result["890201"][0] == 5000
    assert result["Total"][0] == 5000


def test_order_columns_fixed_first_then_cups_sorted(deps):
    uc = _build(deps)
    df = pl.DataFrame({
        "890262-01": [1],
        "Total": [100],
        "Ciudad": ["BOGOTA"],
        "100001": [2],
        "Base": ["X"],
        "NIT": ["900111111"],
        "890207": [3],
    })
    result = uc._order_columns(df)
    cols = result.columns
    # Fixed columns come first in defined order
    assert cols[0] == "Base"
    assert cols[1] == "Ciudad"
    assert cols[2] == "NIT"
    assert cols[3] == "Total"
    # CUP columns sorted numerically
    cup_cols = cols[4:]
    assert cup_cols == ["100001", "890207", "890262-01"]


# ── Tests para _match_companies cascada ───────────────────────────────

def _base_df(nit, empresa):
    return pl.DataFrame({"NIT": [nit], "Empresa": [empresa], "Base": ["X"]})


def test_match_companies_found_in_db(deps):
    """Paso 0: NIT en BD local → actualiza nombre."""
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("900111111", "NOMBRE VIEJO")
    result = uc._match_companies(df, lookups)
    assert result["Empresa"][0] == "EMPRESA A"
    assert result["NIT"][0] == "900111111"


def test_match_companies_rues_by_nit(deps):
    """Paso 1: NIT no en BD, encontrado en RUES por NIT → actualiza nombre."""
    deps["nit_service"] = FakeNitService(
        results=[NitResult(nit=800999999, is_company=True, name="EMPRESA RUES")]
    )
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "NOMBRE ORIGINAL")
    result = uc._match_companies(df, lookups)
    assert result["Empresa"][0] == "EMPRESA RUES"
    assert result["NIT"][0] == "800999999"


def test_match_companies_rues_by_name(deps):
    """Paso 2: NIT no encontrado en RUES, encontrado por nombre → actualiza NIT."""
    deps["nit_service"] = FakeNitService(
        results=[NitResult(nit=800999999, is_company=False)],
        by_name_result=NitResult(nit=700111222, is_company=True, name="EMPRESA X"),
    )
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "EMPRESA X")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "700111222"


def test_match_companies_odoo_by_nit(deps):
    """Paso 3: No en RUES, encontrado en Odoo por NIT → actualiza nombre."""
    deps["nit_service"] = FakeNitService(results=[])
    deps["odoo_repo"] = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "EMPRESA ODOO"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "NOMBRE VIEJO")
    result = uc._match_companies(df, lookups)
    assert result["Empresa"][0] == "EMPRESA ODOO"


def test_match_companies_odoo_by_name(deps):
    """Paso 4: No en RUES ni Odoo/NIT, encontrado en Odoo por nombre → actualiza NIT."""
    deps["nit_service"] = FakeNitService(results=[])
    deps["odoo_repo"] = FakeOdooRepo(clients={"900777777": {"id": 9, "name": "EMPRESA ODOO NAME"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("000000000", "EMPRESA ODOO NAME")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "900777777"


def test_match_companies_not_found_keeps_defaults(deps):
    """Paso 5: No encontrado en ningún lado → datos originales + novedad en log."""
    deps["nit_service"] = FakeNitService(results=[])
    deps["odoo_repo"] = FakeOdooRepo(clients={})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("111111111", "EMPRESA DESCONOCIDA")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "111111111"
    assert result["Empresa"][0] == "EMPRESA DESCONOCIDA"
    assert any("NOVEDAD" in m for m in deps["logger"].warnings)


# ── Tests _match_companies cascada ────────────────────────────────────

def _row(nit, empresa):
    return pl.DataFrame({"NIT": [nit], "Empresa": [empresa], "Base": ["X"]})


def test_match_db_local_updates_nombre(deps):
    """Paso 0: NIT en BD local → actualiza nombre."""
    uc = AssignRatesFromExcel(**deps)
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("900111111", "NOMBRE VIEJO"), lookups)
    assert result["Empresa"][0] == "EMPRESA A"


def test_match_rues_by_nit_updates_nombre(deps):
    """Paso 1: RUES por NIT → actualiza nombre."""
    deps["nit_service"] = FakeNitService(
        results=[NitResult(nit=800999999, is_company=True, name="EMPRESA RUES")]
    )
    uc = AssignRatesFromExcel(**deps)
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "NOMBRE ORIGINAL"), lookups)
    assert result["Empresa"][0] == "EMPRESA RUES"


def test_match_rues_by_name_updates_nit(deps):
    """Paso 2: RUES por nombre → actualiza NIT."""
    deps["nit_service"] = FakeNitService(
        results=[NitResult(nit=800999999, is_company=False)],
        by_name_result=NitResult(nit=700111222, is_company=True, name="EMPRESA X"),
    )
    uc = AssignRatesFromExcel(**deps)
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "EMPRESA X"), lookups)
    assert result["NIT"][0] == "700111222"


def test_match_odoo_by_nit_updates_nombre(deps):
    """Paso 3: Odoo por NIT → actualiza nombre."""
    deps["nit_service"] = FakeNitService(results=[])
    odoo = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "EMPRESA ODOO"}})
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "NOMBRE VIEJO"), lookups)
    assert result["Empresa"][0] == "EMPRESA ODOO"


def test_match_odoo_by_name_updates_nit(deps):
    """Paso 4: Odoo por nombre → actualiza NIT."""
    deps["nit_service"] = FakeNitService(results=[])
    odoo = FakeOdooRepo(clients={"900777777": {"id": 9, "name": "EMPRESA ODOO NAME"}})
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("000000000", "EMPRESA ODOO NAME"), lookups)
    assert result["NIT"][0] == "900777777"


def test_match_not_found_keeps_defaults_and_logs_novedad(deps):
    """Paso 5: No encontrado → datos originales + novedad en log."""
    deps["nit_service"] = FakeNitService(results=[])
    odoo = FakeOdooRepo(clients={})
    logger = FakeLogger()
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo, "logger": logger})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("111111111", "EMPRESA DESCONOCIDA"), lookups)
    assert result["NIT"][0] == "111111111"
    assert result["Empresa"][0] == "EMPRESA DESCONOCIDA"
    assert any("NOVEDAD" in w for w in logger.warnings)
