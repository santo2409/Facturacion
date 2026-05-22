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
        {"nit": "900111111", "company": "DESDE JSON A"},
        {"nit": "900222222", "company": "DESDE JSON B"},
    ]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)

    uc = _build(deps)
    uc._progress_companies(sample_df)
    companies = deps["company_repo"].all()
    names = [c["name"] for c in companies]
    assert "DESDE JSON A" in names


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
