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


def test_assign_paquete_fallback_default(deps):
    """NIT en BD sin paquete asignado → recibe PAQUETE C 2025."""
    deps["company_repo"]._packages = []
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900111111"]})
    result = uc._assign_paquete(df, lookups)
    assert result["PAQUETE"][0] == "PAQUETE C 2025"


def test_assign_paquete_nit_not_in_db_gets_default(deps):
    """NIT que no existe en BD → recibe PAQUETE C 2025 (no queda null)."""
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["999999999"]})
    result = uc._assign_paquete(df, lookups)
    assert result["PAQUETE"][0] == "PAQUETE C 2025"


def test_assign_rates_fallback_to_default_package(deps):
    """Si el paquete de la empresa no tiene tarifa, usa PAQUETE C 2025."""
    # Package id=1 is PAQUETE BASICO (empresa), id=2 is PAQUETE C 2025 (default)
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    # No rate for package 1, but rate exists for default package 2
    deps["rates_repo"]._data[(2, 1, 1, 1, "Package")] = 7500

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
    assert result["890201"][0] == 7500


def test_assign_rates_fallback_logs_warning(deps):
    """Fallback al paquete por defecto genera log de advertencia."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["rates_repo"]._data[(2, 1, 1, 1, "Package")] = 7500

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("PAQUETE C 2025" in w for w in logger.warnings)


def test_assign_rates_wildcard_fallback(deps):
    """Si ni el paquete empresa ni el default tienen tarifa, busca en cualquier otro."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    # Only OTRO PAQUETE (id=3) has rate for city=1, cup=1, activity=1
    deps["rates_repo"]._data[(3, 1, 1, 1, "Package")] = 9999

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
    assert result["890201"][0] == 9999


def test_assign_rates_wildcard_fallback_logs(deps):
    """Wildcard fallback genera log con nombre del paquete fuente."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["rates_repo"]._data[(3, 1, 1, 1, "Package")] = 9999

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("OTRO PAQUETE" in w for w in logger.warnings)
    assert any("BOGOTA" in w for w in logger.warnings)


def test_assign_rates_cup_homologation(deps):
    """CUP con guion sin tarifa → se homologa al CUP base en PAQUETE C 2025."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    # CUP con guion (id=2) y CUP base (id=3)
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 2, "code": "890201-01", "name": "HEMOGRAMA ESP"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    # Solo existe tarifa para el CUP base (890208) en PAQUETE C 2025 (id=2)
    deps["rates_repo"]._data[(2, 1, 3, 1, "Package")] = 42000

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    result = uc._assign_rates(df, lookups)
    assert result["890208-03"][0] == 42000


def test_assign_rates_cup_homologation_logs(deps):
    """Homologación genera log con CUP original y CUP base."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    deps["rates_repo"]._data[(2, 1, 3, 1, "Package")] = 42000

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("890208-03" in w and "890208" in w for w in logger.warnings)
    assert any("PAQUETE C 2025" in w for w in logger.warnings)


def test_assign_rates_no_homologation_without_dash(deps):
    """CUP sin guion no intenta homologación — permanece en 1 si no hay tarifa."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    # No rates at all
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
    assert result["890201"][0] == 1


def test_assign_rates_cup_homologation(deps):
    """CUP con guion sin tarifa → se homologa al CUP base en PAQUETE C 2025."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    # Solo existe tarifa para el CUP base (890208, id=3) en PAQUETE C 2025 (id=2)
    deps["rates_repo"]._data[(2, 1, 3, 1, "Package")] = 42000

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    result = uc._assign_rates(df, lookups)
    assert result["890208-03"][0] == 42000


def test_assign_rates_cup_homologation_logs(deps):
    """Homologación genera log con CUP original y CUP base."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    deps["rates_repo"]._data[(2, 1, 3, 1, "Package")] = 42000

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("890208-03" in w and "890208" in w for w in logger.warnings)
    assert any("PAQUETE C 2025" in w for w in logger.warnings)


def test_assign_rates_no_homologation_without_dash(deps):
    """CUP sin guion no intenta homologación — permanece en 1 si no hay tarifa."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
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
    assert result["890201"][0] == 1


def test_assign_rates_phase6_wildcard_base_cup(deps):
    """Phase 6: CUP con guion sin tarifa en PAQUETE C 2025 → homologa base en cualquier paquete."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    # Solo OTRO PAQUETE (id=3) tiene tarifa para el CUP base 890208 (id=3)
    deps["rates_repo"]._data[(3, 1, 3, 1, "Package")] = 55000

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    result = uc._assign_rates(df, lookups)
    assert result["890208-03"][0] == 55000


def test_assign_rates_phase6_logs_source_package(deps):
    """Phase 6 genera log con CUP original, CUP base y nombre del paquete fuente."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    deps["rates_repo"]._data[(3, 1, 3, 1, "Package")] = 55000

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("890208-03" in w and "890208" in w for w in logger.warnings)
    assert any("OTRO PAQUETE" in w for w in logger.warnings)


def test_assign_rates_phase7_any_city(deps):
    """Phase 7: CUP sin tarifa en ninguna ciudad conocida → toma de otra ciudad."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    # Solo hay tarifa para city_id=99 (otra ciudad), cup=1, activity=1
    deps["rates_repo"]._data[(3, 99, 1, 1, "Package")] = 33000

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
    assert result["890201"][0] == 33000


def test_assign_rates_phase7_logs_ciudad_diferente(deps):
    """Phase 7 genera log con indicación de ciudad diferente."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["rates_repo"]._data[(3, 99, 1, 1, "Package")] = 33000

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("ciudad diferente" in w for w in logger.warnings)
    assert any("OTRO PAQUETE" in w for w in logger.warnings)


def test_assign_rates_phase7_any_city(deps):
    """Phase 7: CUP sin tarifa en ninguna ciudad conocida → toma de otra ciudad."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    # Solo hay tarifa para city_id=99 (otra ciudad), cup=1 (890201), activity=1
    deps["rates_repo"]._data[(3, 99, 1, 1, "Package")] = 33000

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
    assert result["890201"][0] == 33000


def test_assign_rates_phase7_logs_ciudad_diferente(deps):
    """Phase 7 genera log con indicación de ciudad diferente y nombre del paquete fuente."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["rates_repo"]._data[(3, 99, 1, 1, "Package")] = 33000

    logger = FakeLogger()
    deps["logger"] = logger
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    uc._assign_rates(df, lookups)
    assert any("ciudad diferente" in w for w in logger.warnings)
    assert any("OTRO PAQUETE" in w for w in logger.warnings)
