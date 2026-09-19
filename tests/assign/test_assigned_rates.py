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
    result, _ = uc._assign_rates(df, lookups)
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
    result, _ = uc._assign_rates(df, lookups)
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
