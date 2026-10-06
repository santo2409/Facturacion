"""Tests para la resolución de DIRECTORY en la opción 2 (spec 007, RF-06/AC-07)."""

import json

import polars as pl
import pytest

from src.billers.application.use_cases.import_billers_from_excel import ImportBillersFromExcel
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_progress import FakeProgress


@pytest.fixture
def deps():
    return {
        "biller_repo": FakeBillerRepo(),
        "company_repo": FakeCompanyRepo(),
        "biller_company_repo": FakeBillerCompanyRepo(),
        "nit_service": FakeNitService(results=[]),
        "progress": FakeProgress(),
        "fuzz": FakeFuzz(),
        "logger": FakeLogger(),
    }


def test_process_companies_sin_directory_no_lanza_typeerror(deps, monkeypatch):
    monkeypatch.delenv("DIRECTORY", raising=False)
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "GESTOR": ["GESTOR A"],
        "EMPRESA": ["EMPRESA A"],
    })
    uc = ImportBillersFromExcel(**deps)

    uc._process_companies(df)  # no debe lanzar TypeError


def test_process_companies_sin_directory_resuelve_la_ruta_por_defecto(
    deps, tmp_path, monkeypatch
):
    """Primera cláusula del AC-07: "la ruta de trabajo se resuelve con el
    valor por defecto". Evidencia conductual: con DIRECTORY sin definir y el
    directorio de trabajo en tmp_path, el data.json colocado ahí se
    encuentra y el servicio externo no se consulta."""
    monkeypatch.delenv("DIRECTORY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data.json").write_text(
        json.dumps([{"nit": "900111111", "name": "EMPRESA A"}]), encoding="utf-8"
    )
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "GESTOR": ["GESTOR A"],
        "EMPRESA": ["EMPRESA A"],
    })
    uc = ImportBillersFromExcel(**deps)

    uc._process_companies(df)

    assert deps["nit_service"].called_with is None, (
        "se consultó el servicio externo: la caché en el directorio por "
        "defecto no se resolvió"
    )
