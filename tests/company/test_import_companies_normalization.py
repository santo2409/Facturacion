"""Tests del flujo de normalización de documentos y deduplicación de
vinculaciones (spec 006). Vive en un archivo separado de
test_import_companies_from_excel.py para no tocar ese archivo (NF-01)."""

from src.company.domain.entities.company_package import CompanyPackage
from tests.fakes.fake_company_repo import FakeCompanyRepo


def test_fake_company_repo_registra_batches_recibidos():
    repo = FakeCompanyRepo(initial=[{"id": 1, "nit": "900111111", "name": "EMPRESA A"}])
    batch = [CompanyPackage(company_id=1, package_id=10, model="Package")]

    repo.companies_packages_batch(batch)

    assert repo.batches == [batch]
    # comportamiento existente de upsert no se altera
    assert repo.companies_packages_all() == [{"company": 1, "package": 10, "model": "Package"}]


# --- T05: normalización en _progress_companies (fase A) ---

import json as _json

import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import ImportCompaniesFromExcel
from src.company.domain.entities.company import Company as _Company
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo


@pytest.fixture
def deps_t05(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
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


def test_progress_companies_normaliza_nit_con_puntos_y_guiones(deps_t05):
    deps_t05["nit_service"] = FakeNitService(results=[_Company("900111111", "EMPRESA A")])
    df = pl.DataFrame({"NIT": ["900.111.111-1"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    companies = deps_t05["company_repo"].all()
    assert len(companies) == 1
    assert companies[0]["nit"] == "900111111"


def test_progress_companies_conserva_cedula_integra(deps_t05):
    deps_t05["nit_service"] = FakeNitService(results=[_Company("1000017310", "PERSONA X")])
    df = pl.DataFrame({"NIT": ["1000017310"], "RAZON SOCIAL": ["PERSONA X"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    companies = deps_t05["company_repo"].all()
    assert len(companies) == 1
    assert companies[0]["nit"] == "1000017310"


def test_progress_companies_no_reconsulta_documento_ya_normalizado_en_bd(deps_t05):
    deps_t05["company_repo"] = FakeCompanyRepo(
        initial=[{"id": 1, "nit": "900111111", "name": "EMPRESA A"}]
    )
    df = pl.DataFrame({"NIT": ["900.111.111"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert deps_t05["nit_service"].called_with is None


def test_progress_companies_cache_indexada_por_documento_normalizado(deps_t05, tmp_path):
    cache_path = tmp_path / "data.json"
    cache_path.write_text(
        _json.dumps([{"nit": "900111111", "is_company": True, "name": "EMPRESA A CACHED"}]),
        encoding="utf-8",
    )
    df = pl.DataFrame({"NIT": ["900.111.111-1"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert deps_t05["nit_service"].called_with is None
    companies = deps_t05["company_repo"].all()
    assert companies[0]["name"] == "EMPRESA A CACHED"


def test_progress_companies_advierte_dv_invalido(deps_t05):
    deps_t05["nit_service"] = FakeNitService(results=[_Company("900111111", "EMPRESA A")])
    df = pl.DataFrame({"NIT": ["9001111115"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert any("9001111115" in w for w in deps_t05["logger"].warnings)
    assert uc._dv_warning_count == 1


# --- T06: dedup de vinculaciones + reporte de no vinculadas (fase B) ---

from src.company.domain.entities.unlinked_row import UnlinkedRow as _UnlinkedRow
from tests.fakes.fake_not_linked_log_generator import FakeNotLinkedLogGenerator


@pytest.fixture
def deps_t06(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "company_repo": FakeCompanyRepo(
            initial=[
                {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
                {"id": 2, "nit": "900222222", "name": "EMPRESA B"},
            ]
        ),
        "package_repo": FakePackageRepo([{"id": 10, "name": "PAQUETE A"}, {"id": 20, "name": "PAQUETE B"}]),
        "provider_repo": FakeProviderRepo([{"id": 30, "name": "PROVEEDOR DUMMY"}]),
        "special_repo": FakeSpecialRepo([{"id": 40, "name": "ESPECIAL DUMMY"}]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(results=[]),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "not_linked_log_generator": FakeNotLinkedLogGenerator(),
        "logs_dir": tmp_path / "logs",
    }


def test_progress_companies_to_packages_dedup_ultima_fila_gana(deps_t06):
    df = pl.DataFrame({
        "NIT": ["900111111", "900111111"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA A"],
        "PAQUETE": ["PAQUETE A", "PAQUETE B"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc._progress_companies_to_packages(df)

    links = deps_t06["company_repo"].companies_packages_all()
    assert len(links) == 1
    assert links[0]["package"] == 20  # PAQUETE B


def test_progress_companies_to_packages_conflicto_genera_warning(deps_t06):
    df = pl.DataFrame({
        "NIT": ["900111111", "900111111"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA A"],
        "PAQUETE": ["PAQUETE A", "PAQUETE B"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc._progress_companies_to_packages(df)

    warnings = deps_t06["logger"].warnings
    assert any("900111111" in w and "PAQUETE A" in w and "PAQUETE B" in w for w in warnings)


def test_progress_companies_to_packages_lote_sin_duplicados_por_company_id(deps_t06):
    """AC-10 literal: cinco filas, dos comparten documento -> cuatro vinculaciones."""
    deps_t06["company_repo"] = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
        {"id": 2, "nit": "900222222", "name": "EMPRESA B"},
        {"id": 3, "nit": "900333333", "name": "EMPRESA C"},
        {"id": 4, "nit": "900444444", "name": "EMPRESA D"},
    ])
    df = pl.DataFrame({
        "NIT": ["900111111", "900111111", "900222222", "900333333", "900444444"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA A", "EMPRESA B", "EMPRESA C", "EMPRESA D"],
        "PAQUETE": ["PAQUETE A", "PAQUETE B", "PAQUETE A", "PAQUETE A", "PAQUETE B"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc._progress_companies_to_packages(df)

    sent_batch = deps_t06["company_repo"].batches[0]
    company_ids = [cp.company_id for cp in sent_batch]
    assert len(company_ids) == len(set(company_ids)), "el lote no puede repetir company_id"
    assert len(sent_batch) == 4
    assert len(deps_t06["company_repo"].companies_packages_all()) == 4


def test_progress_companies_to_packages_fila_sin_empresa_genera_warning_y_reporte(deps_t06):
    df = pl.DataFrame({
        "NIT": ["900999999"],
        "RAZON SOCIAL": ["EMPRESA FANTASMA"],
        "PAQUETE": ["PAQUETE A"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc._progress_companies_to_packages(df)

    assert any("900999999" in w for w in deps_t06["logger"].warnings)
    calls = deps_t06["not_linked_log_generator"].calls
    assert len(calls) == 1
    rows, _ = calls[0]
    assert len(rows) == 1
    assert rows[0].document == "900999999"
    assert rows[0].company_name == "EMPRESA FANTASMA"


def test_progress_companies_to_packages_sin_filas_no_vinculadas_no_genera_reporte(deps_t06):
    df = pl.DataFrame({
        "NIT": ["900111111"],
        "RAZON SOCIAL": ["EMPRESA A"],
        "PAQUETE": ["PAQUETE A"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc._progress_companies_to_packages(df)

    assert deps_t06["not_linked_log_generator"].calls == []


def test_execute_emite_resumen_agregado_final(deps_t06):
    df = pl.DataFrame({
        "NIT": ["900111111", "900999999"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA FANTASMA"],
        "PAQUETE": ["PAQUETE A", "PAQUETE A"],
    })
    uc = ImportCompaniesFromExcel(**deps_t06)

    uc.execute(df)

    infos = deps_t06["logger"].infos
    assert len(infos) == 1
    resumen = infos[0]
    assert "0 creada(s)" in resumen
    assert "1 vinculación(es) persistida(s)" in resumen
    assert "1 fila(s) sin vincular" in resumen


# --- verify: cierre de huecos de evidencia detectados en la auditoría de AC ---

def test_progress_companies_dv_valido_no_genera_advertencia(deps_t05):
    """AC-03, segunda cláusula: 'Y no se registra advertencia de error de digitación'."""
    deps_t05["nit_service"] = FakeNitService(results=[_Company("900111111", "EMPRESA A")])
    # 9001111110: DV DIAN de 900111111 es 0 -> válido
    df = pl.DataFrame({"NIT": ["9001111110"], "RAZON SOCIAL": ["EMPRESA A"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert deps_t05["company_repo"].all()[0]["nit"] == "900111111"
    assert uc._dv_warning_count == 0
    assert not any("error de digitación" in w for w in deps_t05["logger"].warnings)


def test_progress_companies_persiste_cedula_8_digitos_integra(deps_t05):
    """AC-05 sobre el flujo de persistencia, no solo sobre la función pura."""
    deps_t05["nit_service"] = FakeNitService(results=[_Company("19146113", "PERSONA Y")])
    df = pl.DataFrame({"NIT": ["19146113"], "RAZON SOCIAL": ["PERSONA Y"], "PAQUETE": ["X"]})
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert deps_t05["company_repo"].all()[0]["nit"] == "19146113"


def test_progress_companies_persiste_cedula_corta_prefijo_8_integra(deps_t05):
    """AC-06 sobre el flujo: 8125007 es cédula real de 7 dígitos con prefijo 8."""
    deps_t05["nit_service"] = FakeNitService(
        results=[_Company("8125007", "TABORDA AGUDELO ANDRES FELIPE")]
    )
    df = pl.DataFrame({
        "NIT": ["8125007"],
        "RAZON SOCIAL": ["TABORDA AGUDELO ANDRES FELIPE"],
        "PAQUETE": ["X"],
    })
    uc = ImportCompaniesFromExcel(**deps_t05)

    uc._progress_companies(df)

    assert deps_t05["company_repo"].all()[0]["nit"] == "8125007"
