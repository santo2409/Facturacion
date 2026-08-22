"""Tests para ImportCompaniesFromExcel use case."""
import json

import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import ImportCompaniesFromExcel
from src.company.domain.entities.company import Company
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger


@pytest.fixture
def sample_df():
    return pl.DataFrame({
        "NIT": ["900111111", "900222222"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA B"],
        "PAQUETE": ["PAQUETE BASICO", "TARIFA PROVEEDOR X"],
    })


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "company_repo": FakeCompanyRepo(),
        "package_repo": FakePackageRepo([{"id": 1, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([{"id": 2, "name": "TARIFA PROVEEDOR X"}]),
        "special_repo": FakeSpecialRepo([{"id": 3, "name": "ESPECIAL DUMMY"}]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(results=[
            Company("900111111", "EMPRESA A SCRAPPED"),
            Company("900222222", "EMPRESA B SCRAPPED"),
        ]),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
    }


def _build(deps):
    return ImportCompaniesFromExcel(**deps)


def test_progress_companies_creates_companies(sample_df, deps):
    uc = _build(deps)
    uc._progress_companies(sample_df)
    companies = deps["company_repo"].all()
    assert len(companies) == 2
    nits = [c["nit"] for c in companies]
    assert "900111111" in nits


def test_progress_companies_uses_scrapped_name(sample_df, deps):
    uc = _build(deps)
    uc._progress_companies(sample_df)
    companies = deps["company_repo"].all()
    names = [c["name"] for c in companies]
    assert "EMPRESA A SCRAPPED" in names


def test_progress_companies_uses_data_json_if_exists(sample_df, deps, tmp_path):
    data = [
        {"nit": "900111111", "name": "DESDE JSON A"},
        {"nit": "900222222", "name": "DESDE JSON B"},
    ]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)

    uc = _build(deps)
    uc._progress_companies(sample_df)
    companies = deps["company_repo"].all()
    names = [c["name"] for c in companies]
    assert "DESDE JSON A" in names


def test_progress_companies_skips_scraping_for_nits_already_in_db(sample_df, deps):
    deps["company_repo"] = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "900111111", "name": "EMPRESA A YA CONOCIDA"},
    ])
    tracking = FakeNitService(results=[
        Company("900222222", "EMPRESA B SCRAPPED"),
    ])
    deps["nit_service"] = tracking

    uc = _build(deps)
    uc._progress_companies(sample_df)

    assert tracking.called_with == ["900222222"]


def test_progress_companies_to_packages_links(sample_df, deps):
    # First create companies
    uc = _build(deps)
    uc._progress_companies(sample_df)
    uc._progress_companies_to_packages(sample_df)

    packages = deps["company_repo"]._packages
    assert len(packages) == 2


def test_execute_full_flow(sample_df, deps):
    uc = _build(deps)
    uc.execute(sample_df)

    companies = deps["company_repo"].all()
    packages = deps["company_repo"]._packages
    assert len(companies) == 2
    assert len(packages) == 2


def test_package_not_found_logs_warning(deps):
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "RAZON SOCIAL": ["X"],
        "PAQUETE": ["INEXISTENTE"],
    })
    uc = _build(deps)
    uc.execute(df)
    assert any("not found" in e.lower() or "no se encontró" in e.lower() for e in deps["logger"].warnings)


def test_progress_companies_does_not_update_existing_company_name(sample_df, deps):
    deps["company_repo"] = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "900111111", "name": "NOMBRE ORIGINAL"},
        {"id": 2, "nit": "900222222", "name": "NOMBRE ORIGINAL B"},
    ])
    tracking = FakeNitService(results=[
        Company("900111111", "NOMBRE DIFERENTE DESDE RUES"),
    ])
    deps["nit_service"] = tracking

    uc = _build(deps)
    uc._progress_companies(sample_df)

    companies = deps["company_repo"].all()
    names_by_nit = {c["nit"]: c["name"] for c in companies}
    assert names_by_nit["900111111"] == "NOMBRE ORIGINAL"
    assert names_by_nit["900222222"] == "NOMBRE ORIGINAL B"
    assert tracking.called_with is None


def test_progress_companies_not_found_is_omitted_and_logged(sample_df, deps):
    deps["nit_service"] = FakeNitService(results=[
        Company("900111111", "EMPRESA A SCRAPPED"),
        Company("900222222", None),
    ])

    uc = _build(deps)
    uc._progress_companies(sample_df)

    companies = deps["company_repo"].all()
    nits = [c["nit"] for c in companies]
    assert "900111111" in nits
    assert "900222222" not in nits

    log_gen = deps["not_found_log_generator"]
    assert len(log_gen.calls) == 1
    logged_results, output_dir = log_gen.calls[0]
    assert output_dir == deps["logs_dir"]
    assert [str(r.nit) for r in logged_results] == ["900222222"]
    assert logged_results[0].is_company is False


def test_progress_companies_does_not_create_when_not_verified_despite_display_name(sample_df, deps, tmp_path):
    data = [
        {"nit": "900111111", "is_company": False, "name": "NOMBRE DE EXHIBICION", "checked_bases": "Odoo, RUES"},
        {"nit": "900222222", "is_company": True, "name": "EMPRESA B VERIFICADA", "checked_bases": "Odoo"},
    ]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)

    uc = _build(deps)
    uc._progress_companies(sample_df)

    companies = deps["company_repo"].all()
    nits = [c["nit"] for c in companies]
    assert "900111111" not in nits
    assert "900222222" in nits


def test_progress_companies_not_found_log_uses_razon_social_as_display_name(sample_df, deps):
    deps["nit_service"] = FakeNitService(results=[
        Company("900111111", "EMPRESA A SCRAPPED"),
        Company("900222222", None),
    ])

    uc = _build(deps)
    uc._progress_companies(sample_df)

    log_gen = deps["not_found_log_generator"]
    logged_results, _ = log_gen.calls[0]
    assert logged_results[0].name == "EMPRESA B"


def test_progress_companies_new_company_ignores_razon_social_from_excel(deps):
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "RAZON SOCIAL": ["NOMBRE CRUDO DEL EXCEL"],
        "PAQUETE": ["PAQUETE BASICO"],
    })
    deps["nit_service"] = FakeNitService(results=[
        Company("900111111", "NOMBRE VERIFICADO"),
    ])

    uc = _build(deps)
    uc._progress_companies(df)

    companies = deps["company_repo"].all()
    names = [c["name"] for c in companies]
    assert names == ["NOMBRE VERIFICADO"]
