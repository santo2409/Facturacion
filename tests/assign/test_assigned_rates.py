"""Tests para AssignRatesFromExcel use case."""
import json
import os

import openpyxl
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
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_odoo_repo import FakeOdooRepo
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
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
        "fuzz": FakeFuzz(),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
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
    result, _ = uc._assign_rates(df, lookups)
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
    """Paso 1: NIT no en BD, encontrado en data.json (RUES) por NIT → actualiza nombre."""
    # Write NIT to data.json so scraped_nits picks it up
    import os
    data_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
    with open(data_path, "w") as f:
        json.dump([
            {"nit": "900111111", "name": "EMPRESA A"},
            {"nit": "800999999", "name": "EMPRESA RUES"},
        ], f)
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "NOMBRE ORIGINAL")
    result = uc._match_companies(df, lookups)
    assert result["Empresa"][0] == "EMPRESA RUES"
    assert result["NIT"][0] == "800999999"


def test_match_companies_rues_by_name(deps):
    """Paso 2: NIT no encontrado, encontrado por nombre en data.json → actualiza NIT."""
    import os
    data_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
    with open(data_path, "w") as f:
        json.dump([
            {"nit": "900111111", "name": "EMPRESA A"},
            {"nit": "700111222", "name": "EMPRESA X"},
        ], f)
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "EMPRESA X")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "700111222"


def test_match_companies_odoo_by_nit(deps):
    """Paso 3: No en RUES, encontrado en Odoo por NIT → actualiza nombre."""
    deps["odoo_repo"] = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "EMPRESA ODOO"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "NOMBRE VIEJO")
    result = uc._match_companies(df, lookups)
    assert result["Empresa"][0] == "EMPRESA ODOO"


def test_match_companies_odoo_by_name(deps):
    """Paso 4: No en RUES ni Odoo/NIT, encontrado en Odoo por nombre → actualiza NIT."""
    deps["odoo_repo"] = FakeOdooRepo(clients={"900777777": {"id": 9, "name": "EMPRESA ODOO NAME"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("000000000", "EMPRESA ODOO NAME")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "900777777"


# ── Tests para _validate_empresa (regresión: revertía en silencio el ────
# nombre ya resuelto por Odoo de vuelta al valor desactualizado de BD local,
# invirtiendo la prioridad documentada Odoo > BD local > RUES) ──────────

def test_validate_empresa_respects_odoo_resolution(deps):
    deps["company_repo"] = FakeCompanyRepo([
        {"id": 1, "nit": "800999999", "name": "NOMBRE BD DESACTUALIZADO"},
    ])
    deps["odoo_repo"] = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "NOMBRE ODOO ACTUAL"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("800999999", "NOMBRE EXCEL")
    df = uc._match_companies(df, lookups)
    assert df["Empresa"][0] == "NOMBRE ODOO ACTUAL"

    df = uc._validate_empresa(df, lookups)
    assert df["Empresa"][0] == "NOMBRE ODOO ACTUAL"


def test_validate_empresa_still_corrects_non_odoo_mismatches(deps):
    deps["company_repo"] = FakeCompanyRepo([
        {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
        {"id": 2, "nit": "700111222", "name": "EMPRESA X OFICIAL"},
    ])
    data = [{"nit": "700111222", "name": "EMPRESA X"}]
    with open(os.path.join(os.getenv("DIRECTORY", ""), "data.json"), "w") as f:
        json.dump(data, f)

    uc = _build(deps)
    lookups = uc._build_lookups()
    # NIT del Excel no existe en BD local ni Odoo; se resuelve por RUES/nombre,
    # que solo corrige el NIT y deja "Empresa" tal cual venía del Excel.
    df = _base_df("800999999", "EMPRESA X")
    df = uc._match_companies(df, lookups)
    assert df["NIT"][0] == "700111222"
    assert df["Empresa"][0] == "EMPRESA X"

    df = uc._validate_empresa(df, lookups)
    assert df["Empresa"][0] == "EMPRESA X OFICIAL"


# ── Tests para _connect_odoo (regresión: la conexión a Odoo nunca se ────
# establecía antes de usar el repo en execute(), por lo que el paso "Odoo
# primero" fallaba en silencio en todas las filas) ──────────────────────

def test_connect_odoo_marks_repo_as_connected(deps):
    deps["odoo_repo"] = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "EMPRESA ODOO"}})
    uc = _build(deps)
    uc._connect_odoo()
    assert uc.odoo_repo is not None
    assert uc.odoo_repo._connected is True


def test_connect_odoo_disables_repo_on_failure(deps):
    class FailingOdooRepo(FakeOdooRepo):
        def connect(self):
            raise ConnectionError("Autenticación fallida")

    deps["odoo_repo"] = FailingOdooRepo()
    uc = _build(deps)
    uc._connect_odoo()
    assert uc.odoo_repo is None


def test_connect_odoo_noop_when_no_repo_configured(deps):
    deps["odoo_repo"] = None
    uc = _build(deps)
    uc._connect_odoo()
    assert uc.odoo_repo is None


def test_match_companies_not_found_keeps_defaults(deps):
    """Paso 5: No encontrado en ningún lado → datos originales + novedad en log."""
    deps["odoo_repo"] = FakeOdooRepo(clients={})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("111111111", "EMPRESA DESCONOCIDA")
    result = uc._match_companies(df, lookups)
    assert result["NIT"][0] == "111111111"
    assert result["Empresa"][0] == "EMPRESA DESCONOCIDA"
    assert any("NOVEDAD" in m for m in deps["logger"].warnings)


def test_match_companies_not_found_reports_to_not_found_log(deps):
    """NIT no encontrado en ninguna fuente → se registra en empresas_no_encontradas.xlsx."""
    deps["odoo_repo"] = FakeOdooRepo(clients={})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("111111111", "EMPRESA DESCONOCIDA")
    uc._match_companies(df, lookups)

    log_gen = deps["not_found_log_generator"]
    assert len(log_gen.calls) == 1
    logged_results, output_dir = log_gen.calls[0]
    assert output_dir == deps["logs_dir"]
    assert len(logged_results) == 1
    assert logged_results[0].nit == "111111111"
    assert logged_results[0].is_company is False
    assert logged_results[0].name == "EMPRESA DESCONOCIDA"


def test_match_companies_found_does_not_report_to_not_found_log(deps):
    """NIT resuelto (BD local) → no se reporta a empresas_no_encontradas.xlsx."""
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = _base_df("900111111", "NOMBRE VIEJO")
    uc._match_companies(df, lookups)

    assert deps["not_found_log_generator"].calls == []


def test_match_companies_not_found_dedupes_repeated_nit(deps):
    """La misma empresa aparece en varias filas (una por examen) → una sola entrada en el log."""
    deps["odoo_repo"] = FakeOdooRepo(clients={})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["111111111", "111111111", "111111111"],
        "Empresa": ["EMPRESA DESCONOCIDA"] * 3,
        "Base": ["X", "X", "X"],
    })
    uc._match_companies(df, lookups)

    log_gen = deps["not_found_log_generator"]
    assert len(log_gen.calls) == 1
    logged_results, _ = log_gen.calls[0]
    assert len(logged_results) == 1


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
    """Paso 1: RUES por NIT (data.json) → actualiza nombre."""
    import os
    data_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
    with open(data_path, "w") as f:
        json.dump([
            {"nit": "900111111", "name": "EMPRESA A"},
            {"nit": "800999999", "name": "EMPRESA RUES"},
        ], f)
    uc = AssignRatesFromExcel(**deps)
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "NOMBRE ORIGINAL"), lookups)
    assert result["Empresa"][0] == "EMPRESA RUES"


def test_match_rues_by_name_updates_nit(deps):
    """Paso 2: RUES por nombre (data.json) → actualiza NIT."""
    import os
    data_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
    with open(data_path, "w") as f:
        json.dump([
            {"nit": "900111111", "name": "EMPRESA A"},
            {"nit": "700111222", "name": "EMPRESA X"},
        ], f)
    uc = AssignRatesFromExcel(**deps)
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "EMPRESA X"), lookups)
    assert result["NIT"][0] == "700111222"


def test_match_odoo_by_nit_updates_nombre(deps):
    """Paso 3: Odoo por NIT → actualiza nombre."""
    odoo = FakeOdooRepo(clients={"800999999": {"id": 5, "name": "EMPRESA ODOO"}})
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("800999999", "NOMBRE VIEJO"), lookups)
    assert result["Empresa"][0] == "EMPRESA ODOO"


def test_match_odoo_by_name_updates_nit(deps):
    """Paso 4: Odoo por nombre → actualiza NIT."""
    odoo = FakeOdooRepo(clients={"900777777": {"id": 9, "name": "EMPRESA ODOO NAME"}})
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("000000000", "EMPRESA ODOO NAME"), lookups)
    assert result["NIT"][0] == "900777777"


def test_match_not_found_keeps_defaults_and_logs_novedad(deps):
    """Paso 5: No encontrado → datos originales + novedad en log."""
    odoo = FakeOdooRepo(clients={})
    logger = FakeLogger()
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo, "logger": logger})
    lookups = uc._build_lookups()
    result = uc._match_companies(_row("111111111", "EMPRESA DESCONOCIDA"), lookups)
    assert result["NIT"][0] == "111111111"
    assert result["Empresa"][0] == "EMPRESA DESCONOCIDA"
    assert any("NOVEDAD" in w for w in logger.warnings)


def test_nit_sourced_from_odoo_is_truncated_to_9_digits_before_output(deps):
    """El NIT que llega desde Odoo (get_nit) al hacer match por nombre puede
    venir con más de 9 dígitos; el CONSOLIDADO debe respetar el máximo de 9,
    igual que el NIT normalizado desde el Excel de entrada."""
    odoo = FakeOdooRepo(clients={"900777777123": {"id": 9, "name": "EMPRESA ODOO NAME"}})
    uc = AssignRatesFromExcel(**{**deps, "odoo_repo": odoo})
    lookups = uc._build_lookups()

    df = uc._match_companies(_row("000000000", "EMPRESA ODOO NAME"), lookups)
    assert df["NIT"][0] == "900777777123"  # tal como lo devolvió Odoo, sin truncar

    df = uc._normalize_nit(df)
    assert df["NIT"][0] == "900777777"


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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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


# ── cell_colors tests ─────────────────────────────────────────────────────────

def test_cell_colors_phase2_yellow(deps):
    """Phase 2 (PAQUETE C 2025 mismo CUP) → color FFFF99."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["rates_repo"]._data[(2, 1, 1, 1, "Package")] = 50000  # solo en PAQUETE C 2025

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert colors.get(("890201", 0)) == "FFF2CC"


def test_cell_colors_phase3_orange(deps):
    """Phase 3 (cualquier paquete, mismo CUP, misma ciudad) → color FFD580."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["rates_repo"]._data[(3, 1, 1, 1, "Package")] = 60000  # solo en OTRO PAQUETE

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert colors.get(("890201", 0)) == "F4B183"


def test_cell_colors_phase4_lightblue(deps):
    """Phase 4 (PAQUETE C 2025, CUP base) → color ADD8E6."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
    ])
    deps["cup_repo"] = FakeCupRepo([
        {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
        {"id": 3, "code": "890208", "name": "BASE CUP"},
        {"id": 4, "code": "890208-03", "name": "CUP CON GUION"},
    ])
    deps["rates_repo"]._data[(2, 1, 3, 1, "Package")] = 42000  # PAQUETE C 2025, CUP base

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert colors.get(("890208-03", 0)) == "BDD7EE"


def test_cell_colors_phase5_blue(deps):
    """Phase 5 (cualquier paquete, CUP base, misma ciudad) → color 87CEEB."""
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
    deps["rates_repo"]._data[(3, 1, 3, 1, "Package")] = 55000  # OTRO PAQUETE, CUP base

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890208-03": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert colors.get(("890208-03", 0)) == "9DC3E6"


def test_cell_colors_phase6_lilac(deps):
    """Phase 6 (any package, any city) → color DDA0DD."""
    deps["package_repo"] = FakePackageRepo([
        {"id": 1, "name": "PAQUETE BASICO"},
        {"id": 2, "name": "PAQUETE C 2025"},
        {"id": 3, "name": "OTRO PAQUETE"},
    ])
    deps["rates_repo"]._data[(3, 99, 1, 1, "Package")] = 33000  # otra ciudad (id=99)

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert colors.get(("890201", 0)) == "D5A6E6"


def test_cell_colors_phase1_no_color(deps):
    """Phase 1 (paquete propio) → sin color."""
    deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 80000  # paquete propio

    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "PAQUETE": ["PAQUETE BASICO"],
        "890201": [1],
    })
    _, colors = uc._assign_rates(df, lookups)
    assert ("890201", 0) not in colors


def test_build_lookups_sin_directory_resuelve_al_valor_unico_por_defecto(deps, monkeypatch):
    """spec 007 RF-07: el valor por defecto de DIRECTORY debe venir de la
    misma fuente que el resto del sistema (get_paths_config), no de un
    ``os.getenv("DIRECTORY", "")`` propio que diverge del "." usado en
    otros módulos (p. ej. logging_config.py)."""
    import os as _os

    from src.shared.config import DEFAULT_DIRECTORY

    monkeypatch.delenv("DIRECTORY", raising=False)
    seen_paths = []
    real_exists = _os.path.exists
    monkeypatch.setattr(
        _os.path, "exists", lambda p: seen_paths.append(p) or real_exists(p)
    )
    uc = AssignRatesFromExcel(**deps)

    uc._build_lookups()

    assert seen_paths, "no se consultó ningún data.json"
    expected = _os.path.join(DEFAULT_DIRECTORY, "data.json")
    assert seen_paths[0] == expected, (
        f"json_path usó '{seen_paths[0]}', no el valor por defecto único "
        f"'{expected}'"
    )


# ── T10: _build_lookups — imedical y tian (spec 008) ────────────────────

def test_build_lookups_imedical_map_excluye_filas_noop(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "800050383", "name": "DALIMENTOS LTDA", "nit_success": "800050383", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert lookups["imedical_map"] == {}


def test_build_lookups_imedical_map_excluye_filas_ya_corregidas_por_truncado(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "8000613577", "name": "IMPLANTES Y SISTEMAS ORTOPEDICOS SA", "nit_success": "800061357", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert lookups["imedical_map"] == {}


def test_build_lookups_imedical_map_indexa_por_clave_doble_cruda_y_truncada(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "1015426422", "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ", "nit_success": "860504759", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert lookups["imedical_map"]["1015426422"] == "860504759"
    assert lookups["imedical_map"]["101542642"] == "860504759"


def test_build_lookups_tian_nits_excluye_el_propio_tian_nit(deps, monkeypatch):
    from tests.fakes.fake_tian_repo import FakeTianRepo
    monkeypatch.setenv("TIAN_NIT", "900293402")
    deps["tian_repo"] = FakeTianRepo([
        {"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"},
        {"nit_error": "900293402", "name": "TIAN IPS S A S"},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert "800082633" in lookups["tian_nits"]
    assert "900293402" not in lookups["tian_nits"]
    assert lookups["tian_nit"] == "900293402"


def test_build_lookups_sin_imedical_repo_devuelve_map_vacio(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert lookups["imedical_map"] == {}
    assert lookups["imedical_known_nit_errors"] == set()


def test_build_lookups_sin_tian_repo_devuelve_set_vacio(deps, monkeypatch):
    # Independiente del TIAN_NIT real del .env (otro módulo del proceso puede
    # cargarlo vía load_dotenv durante la suite completa; ver DIRECTORY arriba).
    monkeypatch.delenv("TIAN_NIT", raising=False)
    uc = _build(deps)
    lookups = uc._build_lookups()
    assert lookups["tian_nits"] == set()
    assert lookups["tian_nit"] == ""


# ── T11: _capture_raw_nit + _apply_imedical (spec 008 RF-01..05) ────────

def test_apply_imedical_corrige_nit_del_excel(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "191461130", "name": "HUERTAS COTES MARIO ALBERTO", "nit_success": "19146113", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["191461130"], "Empresa": ["HUERTAS COTES"]})
    df = uc._capture_raw_nit(df)

    result = uc._apply_imedical(df, lookups)

    assert result["NIT"][0] == "19146113"


def test_apply_imedical_usa_nit_crudo_sin_truncar_como_clave(deps):
    """El nit_error de imedical tiene 10 dígitos; el NIT del Excel debe
    matchear con el crudo, sin haber pasado por _normalize_nit (AC-02)."""
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "1015426422", "name": "KONRAD LORENZ", "nit_success": "860504759", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["1015426422"], "Empresa": ["X"]})
    df = uc._capture_raw_nit(df)

    result = uc._apply_imedical(df, lookups)

    assert result["NIT"][0] == "860504759"


def test_apply_imedical_no_cuenta_filas_noop_como_correccion(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "800050383", "name": "DALIMENTOS LTDA", "nit_success": "800050383", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800050383"], "Empresa": ["DALIMENTOS"]})
    df = uc._capture_raw_nit(df)

    result = uc._apply_imedical(df, lookups)

    assert result["NIT"][0] == "800050383"
    assert not any("imedical" in w.lower() for w in deps["logger"].warnings)


def test_apply_imedical_no_cuenta_filas_ya_resueltas_por_truncado(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "8000613577", "name": "IMPLANTES SA", "nit_success": "800061357", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["8000613577"], "Empresa": ["IMPLANTES"]})
    df = uc._capture_raw_nit(df)

    result = uc._apply_imedical(df, lookups)

    # el mapeo no aplica (excluido de imedical_map en _build_lookups),
    # así que el NIT queda tal como venía del Excel
    assert result["NIT"][0] == "8000613577"


def test_apply_imedical_deja_intacto_nit_sin_coincidencia(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900999999"], "Empresa": ["X"]})
    df = uc._capture_raw_nit(df)

    result = uc._apply_imedical(df, lookups)

    assert result["NIT"][0] == "900999999"


def test_apply_imedical_registra_correccion_en_logger_dual(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "191461130", "name": "HUERTAS COTES", "nit_success": "19146113", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["191461130"], "Empresa": ["X"]})
    df = uc._capture_raw_nit(df)

    uc._apply_imedical(df, lookups)

    assert any("191461130" in i and "19146113" in i for i in deps["logger"].infos)


def test_apply_imedical_sin_columna_nit_raw_usa_nit_limpiado(deps):
    """Tolerancia para tests que llaman el método aislado sin pasar por
    _capture_raw_nit."""
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "191461130", "name": "HUERTAS COTES", "nit_success": "19146113", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["191461130"], "Empresa": ["X"]})

    result = uc._apply_imedical(df, lookups)

    assert result["NIT"][0] == "19146113"


def test_apply_imedical_publica_nits_bloqueados_en_lookups(deps):
    """Prerrequisito de T12 (RF-04): _match_companies necesita saber qué NIT
    fueron corregidos por imedical para no dejarlos sobrescribir por las
    ramas que resuelven por nombre."""
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "191461130", "name": "HUERTAS COTES", "nit_success": "19146113", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["191461130"], "Empresa": ["X"]})
    df = uc._capture_raw_nit(df)

    uc._apply_imedical(df, lookups)

    assert lookups["imedical_locked_nits"] == {"19146113"}


def test_apply_imedical_no_bloquea_nits_sin_correccion(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900999999"], "Empresa": ["X"]})
    df = uc._capture_raw_nit(df)

    uc._apply_imedical(df, lookups)

    assert lookups.get("imedical_locked_nits", set()) == set()


# ── T12: lock de NIT corregido por imedical en _match_companies (RF-04) ──

def test_match_companies_imedical_es_final_frente_a_odoo_por_nombre(deps):
    """Un NIT ya corregido por imedical no debe ser sobrescrito por la rama
    Odoo-por-nombre, aunque Odoo devuelva un NIT distinto (AC-06)."""
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={"900555555": {"id": 9, "name": "HUERTAS COTES"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["imedical_locked_nits"] = {"19146113"}
    df = pl.DataFrame({"NIT": ["19146113"], "Empresa": ["HUERTAS COTES"], "Base": ["X"]})

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == "19146113"


def test_match_companies_imedical_es_final_frente_a_bd_local_por_nombre(deps):
    deps["company_repo"]._data.append({"id": 99, "nit": "900777777", "name": "HUERTAS COTES"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["imedical_locked_nits"] = {"19146113"}
    df = pl.DataFrame({"NIT": ["19146113"], "Empresa": ["HUERTAS COTES"], "Base": ["X"]})

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == "19146113"


def test_match_companies_imedical_es_final_frente_a_rues_por_nombre(deps, tmp_path):
    import json
    data = [{"nit": "900888888", "name": "HUERTAS COTES"}]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["imedical_locked_nits"] = {"19146113"}
    df = pl.DataFrame({"NIT": ["19146113"], "Empresa": ["HUERTAS COTES"], "Base": ["X"]})

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == "19146113"


def test_match_companies_imedical_permite_que_odoo_corrija_nombre_sin_tocar_nit(deps):
    """La rama por NIT (Odoo-por-NIT) sí puede actualizar el nombre; el NIT
    bloqueado no cambia (AC-07)."""
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={"19146113": {"id": 9, "name": "HUERTAS COTES MARIO ALBERTO"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["imedical_locked_nits"] = {"19146113"}
    df = pl.DataFrame({"NIT": ["19146113"], "Empresa": ["HUERTAS COTES"], "Base": ["X"]})

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == "19146113"
    assert result["Empresa"][0] == "HUERTAS COTES MARIO ALBERTO"


def test_match_companies_imedical_logea_novedad_cuando_una_fuente_discrepa(deps):
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={"900555555": {"id": 9, "name": "HUERTAS COTES"}})
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["imedical_locked_nits"] = {"19146113"}
    df = pl.DataFrame({"NIT": ["19146113"], "Empresa": ["HUERTAS COTES"], "Base": ["X"]})

    uc._match_companies(df, lookups)

    assert any(
        "imedical" in msg.lower() and "900555555" in msg
        for msg in deps["logger"].infos
    )


# ── T13: _apply_tian (spec 008 RF-12..20) ────────────────────────────────

def _tian_deps(deps, monkeypatch, tian_rows=None, tian_nit="900293402", tian_has_package=True):
    from tests.fakes.fake_tian_repo import FakeTianRepo
    from tests.fakes.fake_tian_log_generator import FakeTianLogGenerator
    monkeypatch.setenv("TIAN_NIT", tian_nit)
    deps["company_repo"]._data.append({"id": 255, "nit": tian_nit, "name": "TIAN IPS S A S"})
    if tian_has_package:
        deps["company_repo"]._packages.append({"company": 255, "package": 6, "model": "Special"})
    deps["tian_repo"] = FakeTianRepo(tian_rows or [])
    deps["tian_log_generator"] = FakeTianLogGenerator()
    return deps


def test_apply_tian_reemplaza_nit_por_tian_nit(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    deps["company_repo"]._data.append({"id": 629, "nit": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["LABORATORIOS DERMANAT SAS"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "900293402"


def test_apply_tian_agrega_sufijo_con_nombre_canonico_de_bd(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    deps["company_repo"]._data.append({"id": 629, "nit": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["LABORATORIOS DERMANAT SAS"]})

    result = uc._apply_tian(df, lookups)

    assert result["Empresa"][0] == "LABORATORIOS DERMANAT S.A.S(TIAN)"


def test_apply_tian_usa_nombre_del_excel_si_empresa_no_esta_en_bd(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["DEL EXCEL SAS"]})

    result = uc._apply_tian(df, lookups)

    assert result["Empresa"][0] == "DEL EXCEL SAS(TIAN)"


def test_apply_tian_sufijo_es_idempotente(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    deps["company_repo"]._data.append({"id": 629, "nit": "800082633", "name": "LABORATORIOS DERMANAT S.A.S(TIAN)"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    result = uc._apply_tian(df, lookups)

    assert result["Empresa"][0] == "LABORATORIOS DERMANAT S.A.S(TIAN)"


def test_apply_tian_no_redirige_la_propia_tian(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[
        {"nit_error": "800082633", "name": "X"},
        {"nit_error": "900293402", "name": "TIAN IPS"},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["900293402"], "Empresa": ["TIAN IPS S A S"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "900293402"
    assert result["Empresa"][0] == "TIAN IPS S A S"


def test_apply_tian_considera_nit_crudo_y_corregido_por_imedical(deps, monkeypatch):
    """El NIT ya corregido por imedical (RF-01) debe poder caer en tian (AC-21)."""
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    # simula que _apply_imedical ya corrigió el NIT crudo a 800082633
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"], "_NIT_RAW": ["1015426422"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "900293402"


def test_apply_tian_aborta_si_tian_nit_no_esta_en_env(deps, monkeypatch):
    from tests.fakes.fake_tian_repo import FakeTianRepo
    monkeypatch.delenv("TIAN_NIT", raising=False)
    deps["tian_repo"] = FakeTianRepo([{"nit_error": "800082633", "name": "X"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "800082633"
    assert not result["NIT"].is_null().any()
    assert any("TIAN_NIT" in e for e in deps["logger"].errors)


def test_apply_tian_aborta_si_tian_nit_no_existe_en_companies(deps, monkeypatch):
    from tests.fakes.fake_tian_repo import FakeTianRepo
    from tests.fakes.fake_tian_log_generator import FakeTianLogGenerator
    monkeypatch.setenv("TIAN_NIT", "900293402")
    deps["tian_repo"] = FakeTianRepo([{"nit_error": "800082633", "name": "X"}])
    deps["tian_log_generator"] = FakeTianLogGenerator()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "800082633"
    assert any("900293402" in e for e in deps["logger"].errors)
    assert deps["tian_log_generator"].calls == []


def test_apply_tian_aborta_si_tian_nit_no_tiene_paquete_asignado(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}], tian_has_package=False)
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "800082633"
    assert any("paquete" in e.lower() for e in deps["logger"].errors)


def test_apply_tian_publica_tian_rerouted_nits_en_lookups(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    uc._apply_tian(df, lookups)

    assert lookups.get("tian_rerouted_nits") == {"900293402"}


def test_apply_tian_acumula_tian_assignment_por_nit_original_con_conteo_de_filas(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["800082633", "800082633", "900111111"],
        "Empresa": ["DERMANAT", "DERMANAT", "EMPRESA A"],
    })

    uc._apply_tian(df, lookups)

    calls = deps["tian_log_generator"].calls
    assert len(calls) == 1
    rows, output_dir = calls[0]
    assert len(rows) == 1
    assert rows[0].nit_original == "800082633"
    assert rows[0].rows == 2
    assert output_dir == deps["logs_dir"]


def test_apply_tian_invoca_generador_con_logs_dir(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    uc._apply_tian(df, lookups)

    assert len(deps["tian_log_generator"].calls) == 1
    _, output_dir = deps["tian_log_generator"].calls[0]
    assert output_dir == deps["logs_dir"]


def test_apply_tian_sin_generador_configurado_no_falla(deps, monkeypatch):
    _tian_deps(deps, monkeypatch, tian_rows=[{"nit_error": "800082633", "name": "X"}])
    deps["tian_log_generator"] = None
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({"NIT": ["800082633"], "Empresa": ["X"]})

    result = uc._apply_tian(df, lookups)

    assert result["NIT"][0] == "900293402"


# ── T14: escape de tian_rerouted_nits en _validate_empresa (AC-22) ──────

def test_validate_empresa_no_pisa_nombre_con_sufijo_tian(deps):
    deps["company_repo"]._data.append({"id": 255, "nit": "900293402", "name": "TIAN IPS S A S"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    lookups["tian_rerouted_nits"] = {"900293402"}
    df = pl.DataFrame({
        "NIT": ["900293402"],
        "Empresa": ["LABORATORIOS DERMANAT S.A.S(TIAN)"],
    })

    result = uc._validate_empresa(df, lookups)

    assert result["Empresa"][0] == "LABORATORIOS DERMANAT S.A.S(TIAN)"


# ── T15: auto-registro en imedical (rama 1.5 de _match_companies) ───────
# spec 008 RF-06..RF-11

class _OdooRepoConNombreFijo:
    """Fake mínimo: find_client_by_name siempre devuelve el mismo (id, nombre),
    sin exigir igualdad exacta con el nombre buscado — permite simular que
    Odoo confirma un candidato cuyo nombre difiere del Excel (AC-12)."""

    def __init__(self, nit, name):
        self._nit = nit
        self._name = name

    def find_client(self, nit, name):
        return None, None, None

    def find_client_by_name(self, name):
        return 1, self._name, "nombre"

    def get_nit(self, client_id):
        return self._nit


def test_autoregistro_cuando_base_imedical_y_odoo_confirma_por_nombre(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    saved = deps["imedical_repo"].saved_batches
    assert len(saved) == 1
    assert len(saved[0]) == 1


def test_autoregistro_guarda_nit_error_crudo_sin_truncar(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    correccion = deps["imedical_repo"].saved_batches[0][0]
    assert correccion.nit_error == "1015426422"
    assert correccion.nit_success == "860504759"


def test_autoregistro_guarda_ambos_nombres_correcto_y_del_excel(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    correccion = deps["imedical_repo"].saved_batches[0][0]
    assert correccion.name == "FUNDACION UNIVERSITARIA KONRAD LORENZ"
    assert correccion.name_error == "FUNDACION UNIVERSITARIA KONRAD LORENZ"


def test_autoregistro_no_se_dispara_si_base_no_contiene_imedical(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["SOANDES JULIO"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []


def test_autoregistro_detecta_imedical_como_subcadena_case_insensitive(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["imedical agosto 1-20"],
    })

    uc._match_companies(df, lookups)

    assert len(deps["imedical_repo"].saved_batches) == 1


def test_autoregistro_no_se_dispara_si_similitud_de_nombre_es_baja(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860504759", "EMPRESA TOTALMENTE DIFERENTE SAS")
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []


def test_autoregistro_no_registra_si_nit_resuelto_igual_al_del_excel(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("900555555", "FUNDACION UNIVERSITARIA KONRAD LORENZ")
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["900555555"],
        "_NIT_RAW": ["900555555"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []


def test_autoregistro_no_registra_si_truncado_a_9_ya_corrige(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("800061357", "IMPLANTES Y SISTEMAS ORTOPEDICOS SA")
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["800061357"],
        "_NIT_RAW": ["8000613577"],
        "Empresa": ["IMPLANTES Y SISTEMAS ORTOPEDICOS SA"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []


def test_autoregistro_no_registra_nit_ya_presente_en_imedical(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860504759", "FUNDACION UNIVERSITARIA KONRAD LORENZ")
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "1015426422", "name": "X", "nit_success": "Y", "name_error": None},
    ])
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []


def test_autoregistro_deduplica_nit_repetido_en_la_misma_corrida(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860504759", "FUNDACION UNIVERSITARIA KONRAD LORENZ")
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"] * 3,
        "_NIT_RAW": ["1015426422"] * 3,
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"] * 3,
        "Base": ["IMEDICAL AGOSTO 1-20"] * 3,
    })

    uc._match_companies(df, lookups)

    assert len(deps["imedical_repo"].saved_batches) == 1
    assert len(deps["imedical_repo"].saved_batches[0]) == 1


def test_autoregistro_escribe_en_una_sola_llamada_batch(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo

    class _OdooRepoDosEmpresas:
        def find_client(self, nit, name):
            return None, None, None

        def find_client_by_name(self, name):
            mapa = {
                "FUNDACION UNIVERSITARIA KONRAD LORENZ": (1, "FUNDACION UNIVERSITARIA KONRAD LORENZ"),
                "ADECCO SERVICIOS COLOMBIA SA": (2, "ADECCO SERVICIOS COLOMBIA SA"),
            }
            cid, cname = mapa.get(name, (None, None))
            return cid, cname, "nombre"

        def get_nit(self, client_id):
            return {1: "860504759", 2: "830050228"}.get(client_id)

    deps["odoo_repo"] = _OdooRepoDosEmpresas()
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642", "114087658"],
        "_NIT_RAW": ["1015426422", "1140876585"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ", "ADECCO SERVICIOS COLOMBIA SA"],
        "Base": ["IMEDICAL AGOSTO 1-20", "IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert len(deps["imedical_repo"].saved_batches) == 1
    assert len(deps["imedical_repo"].saved_batches[0]) == 2


def test_autoregistro_tolera_ausencia_de_columna_base(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860504759", "FUNDACION UNIVERSITARIA KONRAD LORENZ")
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
    })

    uc._match_companies(df, lookups)

    assert deps["imedical_repo"].saved_batches == []
    assert any("base" in w.lower() for w in deps["logger"].warnings)


def test_autoregistro_sin_imedical_repo_configurado_no_escribe(deps):
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860504759", "FUNDACION UNIVERSITARIA KONRAD LORENZ")
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == "860504759"


def test_autoregistro_no_anade_llamadas_extra_a_odoo(deps):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    odoo = FakeOdooRepo(clients={
        "860504759": {"id": 9, "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"},
    })
    llamadas = []
    original = odoo.find_client_by_name

    def contando(name):
        llamadas.append(name)
        return original(name)

    odoo.find_client_by_name = contando
    deps["odoo_repo"] = odoo
    deps["imedical_repo"] = FakeImedicalRepo()
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["101542642"],
        "_NIT_RAW": ["1015426422"],
        "Empresa": ["FUNDACION UNIVERSITARIA KONRAD LORENZ"],
        "Base": ["IMEDICAL AGOSTO 1-20"],
    })

    uc._match_companies(df, lookups)

    assert llamadas == ["FUNDACION UNIVERSITARIA KONRAD LORENZ"]


# ── T16: nombre canónico por NIT al cierre de _match_companies (RF-21/22) ─

def test_unifica_variantes_de_nombre_con_mismo_nit_al_nombre_de_bd(deps):
    """Tres filas del mismo NIT con variantes de nombre deben terminar con
    la misma razón social, tomada de BD local (AC-26)."""
    deps["company_repo"]._data.append({"id": 397, "nit": "860050906", "name": "ADECCO COLOMBIA SA"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["860050906", "860050906", "860050906"],
        "Empresa": ["ADECCO COLOMBIA SA", "ADECCO COLOMBIA S.A", "ADECCO COLOMBIA"],
        "Base": ["X", "X", "X"],
    })

    result = uc._match_companies(df, lookups)

    nombres = set(result["Empresa"].to_list())
    assert nombres == {"ADECCO COLOMBIA SA"}


def test_unificacion_prioriza_nombre_de_odoo_sobre_bd_local(deps):
    from tests.fakes.fake_odoo_repo import FakeOdooRepo
    deps["odoo_repo"] = FakeOdooRepo(clients={"860050906": {"id": 1, "name": "ADECCO COLOMBIA SAS (ODOO)"}})
    deps["company_repo"]._data.append({"id": 397, "nit": "860050906", "name": "ADECCO COLOMBIA SA"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["860050906", "860050906"],
        "Empresa": ["ADECCO COLOMBIA SAS (ODOO)", "ADECCO COLOMBIA S.A"],
        "Base": ["X", "X"],
    })

    result = uc._match_companies(df, lookups)

    nombres = set(result["Empresa"].to_list())
    assert nombres == {"ADECCO COLOMBIA SAS (ODOO)"}


def test_unificacion_no_fusiona_empresas_distintas_con_nombre_parecido(deps):
    """ADECCO COLOMBIA SA y ADECCO SERVICIOS COLOMBIA SA son dos clientes
    distintos, con NIT distintos: deben conservar sus nombres (AC-27)."""
    deps["company_repo"]._data.append({"id": 397, "nit": "860050906", "name": "ADECCO COLOMBIA SA"})
    deps["company_repo"]._data.append({"id": 487, "nit": "830050228", "name": "ADECCO SERVICIOS COLOMBIA SA"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["860050906", "830050228"],
        "Empresa": ["ADECCO COLOMBIA SA", "ADECCO SERVICIOS COLOMBIA SA"],
        "Base": ["X", "X"],
    })

    result = uc._match_companies(df, lookups)

    assert result["Empresa"][0] == "ADECCO COLOMBIA SA"
    assert result["Empresa"][1] == "ADECCO SERVICIOS COLOMBIA SA"


def test_unificacion_es_estrictamente_por_nit_no_por_similitud(deps):
    """Dos NIT distintos con nombres casi idénticos en el Excel NO deben
    fusionarse por parecido; cada uno conserva su propio nombre de BD."""
    deps["company_repo"]._data.append({"id": 1, "nit": "111111111", "name": "EMPRESA UNO SAS"})
    deps["company_repo"]._data.append({"id": 2, "nit": "222222222", "name": "EMPRESA DOS SAS"})
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["111111111", "222222222"],
        "Empresa": ["EMPRESA UNO SAS", "EMPRESA DOS SAS"],
        "Base": ["X", "X"],
    })

    result = uc._match_companies(df, lookups)

    assert result["Empresa"][0] == "EMPRESA UNO SAS"
    assert result["Empresa"][1] == "EMPRESA DOS SAS"


def test_unificacion_ignora_filas_con_nit_vacio(deps):
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["", ""],
        "Empresa": ["EMPRESA X", "EMPRESA Y"],
        "Base": ["X", "X"],
    })

    result = uc._match_companies(df, lookups)

    assert result["Empresa"][0] == "EMPRESA X"
    assert result["Empresa"][1] == "EMPRESA Y"


def test_unificacion_cierra_hueco_de_ramas_por_nombre_que_no_actualizan_empresa(deps):
    """Caso límite: dos filas con NIT distintos en el Excel (ninguno conocido
    en BD) resueltas ambas por Odoo-por-nombre al MISMO NIT final. Las ramas
    1.5/3.5 no tocan `Empresa` (dejan el texto crudo del Excel), así que sin
    un epílogo de canonización el mismo NIT final queda con dos nombres
    distintos — justo lo que RF-21 prohíbe."""
    deps["odoo_repo"] = _OdooRepoConNombreFijo("860050906", "ADECCO COLOMBIA SA")
    uc = _build(deps)
    lookups = uc._build_lookups()
    df = pl.DataFrame({
        "NIT": ["999000001", "999000002"],
        "Empresa": ["ADECCO COLOMBIA VARIANTE A", "ADECCO COLOMBIA VARIANTE B"],
        "Base": ["X", "X"],
    })

    result = uc._match_companies(df, lookups)

    assert result["NIT"][0] == result["NIT"][1] == "860050906"
    nombres = set(result["Empresa"].to_list())
    assert len(nombres) == 1


# ── T17: integración en execute() (spec 008) ─────────────────────────────

def _full_row(**overrides):
    base = {
        "NIT": "800082633",
        "Empresa": "LABORATORIOS DERMANAT S.A.S",
        "Base": "GENERAL",
        "Ciudad": "BOGOTA",
        "TIPO DE ACTIVIDAD": "INTRA",
        "Fecha Ingreso": "01/01/2025",
        "Empresa Misión": "",
        "Sede": "",
        "Medio de Pago": "",
        "Tipo Examen": "",
        "Cargo": "",
        "Paciente": "PACIENTE X",
        "N° Identificación": "111",
        "890201": 1,
    }
    base.update(overrides)
    return base


def test_execute_aplica_imedical_antes_de_match_companies(deps, monkeypatch, tmp_path):
    """El NIT crudo de imedical (10 dígitos) debe corregirse antes de que
    _match_companies intente resolverlo por cualquier otra vía."""
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    monkeypatch.chdir(tmp_path)
    deps["company_repo"]._data.append({"id": 629, "nit": "860504759", "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ"})
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "1015426422", "name": "FUNDACION UNIVERSITARIA KONRAD LORENZ", "nit_success": "860504759", "name_error": None},
    ])
    uc = _build(deps)
    df = pl.DataFrame([_full_row(NIT="1015426422", Empresa="KONRAD LORENZ")])
    df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    uc.execute(df, df_facture)

    wb = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    ws = wb["Consolidado"]
    headers = [c.value for c in ws[1]]
    nit_col = headers.index("NIT") + 1
    assert ws.cell(2, nit_col).value == "860504759"


def test_execute_aplica_tian_despues_de_normalize_columns_y_antes_de_asignar_paquete(deps, monkeypatch, tmp_path):
    from tests.fakes.fake_tian_repo import FakeTianRepo
    from tests.fakes.fake_tian_log_generator import FakeTianLogGenerator
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TIAN_NIT", "900293402")
    deps["company_repo"]._data.append({"id": 255, "nit": "900293402", "name": "TIAN IPS S A S"})
    deps["company_repo"]._packages.append({"company": 255, "package": 6, "model": "Special"})
    deps["company_repo"]._data.append({"id": 629, "nit": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"})
    deps["tian_repo"] = FakeTianRepo([{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    deps["tian_log_generator"] = FakeTianLogGenerator()
    uc = _build(deps)
    df = pl.DataFrame([_full_row()])
    df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    uc.execute(df, df_facture)

    wb = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    ws = wb["Consolidado"]
    headers = [c.value for c in ws[1]]
    nit_col = headers.index("NIT") + 1
    empresa_col = headers.index("Empresa") + 1
    assert ws.cell(2, nit_col).value == "900293402"
    assert ws.cell(2, empresa_col).value == "LABORATORIOS DERMANAT S.A.S(TIAN)"


def test_execute_fila_tian_hereda_paquete_y_facturador_de_tian(deps, monkeypatch, tmp_path):
    """AC-19: una empresa de tian SIN paquete propio usa las tarifas de TIAN
    (Special id=6), no el PAQUETE C 2025 por defecto."""
    from tests.fakes.fake_tian_repo import FakeTianRepo
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TIAN_NIT", "900293402")
    deps["company_repo"]._data.append({"id": 255, "nit": "900293402", "name": "TIAN IPS S A S"})
    deps["company_repo"]._packages.append({"company": 255, "package": 6, "model": "Special"})
    deps["tian_repo"] = FakeTianRepo([{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    deps["biller_company_repo"]._data.append({"company": 255, "biller": 1})
    # tarifa de TIAN (Special 6) distinta a cualquier tarifa por defecto
    deps["rates_repo"]._data[(6, 1, 1, 1, "Special")] = 99999
    uc = _build(deps)
    df = pl.DataFrame([_full_row()])
    df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    uc.execute(df, df_facture)

    wb = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    ws = wb["Consolidado"]
    headers = [c.value for c in ws[1]]
    cup_col = headers.index("890201") + 1
    facturador_col = headers.index("FACTURADOR") + 1
    assert ws.cell(2, cup_col).value == 99999
    assert ws.cell(2, facturador_col).value == "ALFA"


def test_execute_no_deja_columnas_auxiliares_en_el_resultado(deps, monkeypatch, tmp_path):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    from tests.fakes.fake_tian_repo import FakeTianRepo
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TIAN_NIT", "900293402")
    deps["company_repo"]._data.append({"id": 255, "nit": "900293402", "name": "TIAN IPS S A S"})
    deps["company_repo"]._packages.append({"company": 255, "package": 6, "model": "Special"})
    deps["imedical_repo"] = FakeImedicalRepo()
    deps["tian_repo"] = FakeTianRepo([{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}])
    uc = _build(deps)
    df = pl.DataFrame([_full_row()])
    df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    uc.execute(df, df_facture)

    wb = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    ws = wb["Consolidado"]
    headers = [c.value for c in ws[1]]
    assert "_NIT_RAW" not in headers
    assert not any(str(h).startswith("_") for h in headers if h)


def test_execute_es_idempotente_en_segunda_corrida_sobre_el_mismo_excel(deps, monkeypatch, tmp_path):
    from tests.fakes.fake_imedical_repo import FakeImedicalRepo
    monkeypatch.chdir(tmp_path)
    deps["company_repo"]._data.append({"id": 629, "nit": "19146113", "name": "HUERTAS COTES MARIO ALBERTO"})
    deps["imedical_repo"] = FakeImedicalRepo([
        {"nit_error": "191461130", "name": "HUERTAS COTES MARIO ALBERTO", "nit_success": "19146113", "name_error": None},
    ])
    uc = _build(deps)
    df = pl.DataFrame([_full_row(NIT="191461130", Empresa="HUERTAS COTES")])
    df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    uc.execute(df, df_facture)
    wb1 = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    rows1 = [tuple(r) for r in wb1["Consolidado"].iter_rows(values_only=True)]

    uc2 = _build(deps)
    df2 = pl.DataFrame([_full_row(NIT="191461130", Empresa="HUERTAS COTES")])
    uc2.execute(df2, df_facture)
    wb2 = openpyxl.load_workbook(tmp_path / "CONSOLIDADO.xlsx")
    rows2 = [tuple(r) for r in wb2["Consolidado"].iter_rows(values_only=True)]

    assert rows1 == rows2
    assert len(deps["imedical_repo"].saved_batches) == 0
