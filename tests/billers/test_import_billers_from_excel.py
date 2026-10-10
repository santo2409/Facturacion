"""Tests para ImportBillersFromExcel use case."""
import json
import os

import polars as pl
import pytest

from src.billers.application.use_cases.import_billers_from_excel import ImportBillersFromExcel
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from src.company.domain.entities.company import Company


@pytest.fixture
def sample_df():
    return pl.DataFrame({
        "NIT": ["900111111", "900222222", "900333333"],
        "GESTOR": ["ALFA", "BETA", "ALFA"],
        "EMPRESA": ["EMPRESA A", "EMPRESA B", "EMPRESA C"],
    })


@pytest.fixture
def use_case_deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    biller_repo = FakeBillerRepo()
    company_repo = FakeCompanyRepo()
    biller_company_repo = FakeBillerCompanyRepo()
    nit_service = FakeNitService(results=[
        Company("900111111", "EMPRESA A REAL"),
        Company("900222222", "EMPRESA B REAL"),
        Company("900333333", "EMPRESA C REAL"),
    ])
    progress = FakeProgress()
    fuzz = FakeFuzz()
    logger = FakeLogger()
    return {
        "biller_repo": biller_repo,
        "company_repo": company_repo,
        "biller_company_repo": biller_company_repo,
        "nit_service": nit_service,
        "progress": progress,
        "fuzz": fuzz,
        "logger": logger,
    }


def _build_use_case(deps):
    return ImportBillersFromExcel(**deps)


def test_process_billers_saves_unique_names(sample_df, use_case_deps):
    uc = _build_use_case(use_case_deps)
    uc._process_billers(sample_df)
    names = [b["name"] for b in use_case_deps["biller_repo"].all()]
    assert "ALFA" in names
    assert "BETA" in names
    assert len(names) == 2  # ALFA appears twice but saved once


def test_process_billers_ignores_nan(use_case_deps):
    df = pl.DataFrame({"NIT": ["900111111"], "GESTOR": ["NAN"], "EMPRESA": ["X"]})
    uc = _build_use_case(use_case_deps)
    uc._process_billers(df)
    assert use_case_deps["biller_repo"].all() == []


def test_process_billers_ignores_none_string(use_case_deps):
    df = pl.DataFrame({"NIT": ["900111111"], "GESTOR": ["NONE"], "EMPRESA": ["X"]})
    uc = _build_use_case(use_case_deps)
    uc._process_billers(df)
    assert use_case_deps["biller_repo"].all() == []


def test_process_companies_creates_companies_and_links(sample_df, use_case_deps):
    uc = _build_use_case(use_case_deps)
    # First create billers so linking works
    uc._process_billers(sample_df)
    uc._process_companies(sample_df)

    companies = use_case_deps["company_repo"].all()
    assert len(companies) == 3

    links = use_case_deps["biller_company_repo"].all()
    assert len(links) == 3


def test_execute_full_flow(sample_df, use_case_deps):
    uc = _build_use_case(use_case_deps)
    uc.execute(sample_df)

    billers = use_case_deps["biller_repo"].all()
    companies = use_case_deps["company_repo"].all()
    links = use_case_deps["biller_company_repo"].all()

    assert len(billers) == 2
    assert len(companies) == 3
    assert len(links) == 3


def test_uses_existing_data_json_only_as_rues_cache(sample_df, use_case_deps, tmp_path, monkeypatch):
    # spec 016: Odoo es la fuente de verdad. El data.json existente ya no decide los
    # nombres: solo aporta, vía el cargador, las entradas cuya fuente es RUES.
    from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache

    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    data = [
        {"nit": "900111111", "name": "DESDE RUES A", "is_company": True, "source": "RUES/NIT"},
        {"nit": "900222222", "name": "DESDE ODOO B", "is_company": True, "source": "Odoo/NIT"},
        {"nit": "900333333", "name": "FORMATO VIEJO C", "is_company": True},
    ]
    with open(tmp_path / "data.json", "w") as f:
        json.dump(data, f)

    uc = ImportBillersFromExcel(**use_case_deps, rues_cache_loader=load_rues_cache)
    uc.execute(sample_df)

    assert list(use_case_deps["nit_service"].rues_cache) == ["900111111"]
    names = [c["name"] for c in use_case_deps["company_repo"].all()]
    assert "DESDE RUES A" not in names and "DESDE ODOO B" not in names  # los nombres vienen de la búsqueda


def test_fuzz_matching_resolves_biller_name(use_case_deps):
    # Configure fuzz to map "ALFAA" -> "ALFA"
    use_case_deps["fuzz"] = FakeFuzz(override={"ALFAA": "ALFA"})
    use_case_deps["biller_repo"] = FakeBillerRepo([{"id": 1, "name": "ALFA"}])

    df = pl.DataFrame({"NIT": ["900111111"], "GESTOR": ["ALFAA"], "EMPRESA": ["X"]})
    uc = _build_use_case(use_case_deps)
    uc._process_billers(df)

    names = [b["name"] for b in use_case_deps["biller_repo"].all()]
    assert "ALFA" in names
