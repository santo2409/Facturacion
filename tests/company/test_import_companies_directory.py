"""Tests para la resolución de DIRECTORY en la opción 5 (spec 007, RF-06/AC-06)."""

import json
from pathlib import Path

import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import ImportCompaniesFromExcel
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo


@pytest.fixture
def deps(tmp_path):
    return {
        "company_repo": FakeCompanyRepo(),
        "package_repo": FakePackageRepo([{"id": 1, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([]),
        "special_repo": FakeSpecialRepo([]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(results=[]),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
    }


def test_progress_companies_sin_directory_no_lanza_typeerror(deps, monkeypatch):
    monkeypatch.delenv("DIRECTORY", raising=False)
    df = pl.DataFrame({"NIT": ["900111111"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(df)  # no debe lanzar TypeError


def test_progress_companies_sin_directory_resuelve_la_ruta_por_defecto(
    deps, tmp_path, monkeypatch
):
    """Primera cláusula del AC-06: "la ruta de trabajo se resuelve con el
    valor por defecto". Evidencia conductual: con DIRECTORY sin definir y el
    directorio de trabajo en tmp_path, un data.json colocado ahí (es decir,
    en ".") debe ser encontrado y reutilizado, de modo que el servicio
    externo no se consulta."""
    monkeypatch.delenv("DIRECTORY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data.json").write_text(
        json.dumps([{"nit": "900111111", "name": "EMPRESA A", "is_company": True}]),
        encoding="utf-8",
    )
    df = pl.DataFrame({"NIT": ["900111111"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(df)

    assert deps["nit_service"].called_with is None, (
        "se consultó el servicio externo: la caché en el directorio por "
        "defecto no se resolvió"
    )
    assert deps["company_repo"].all()[0]["nit"] == "900111111"
