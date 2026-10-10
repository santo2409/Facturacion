"""Opción 5: Odoo como fuente de verdad también para los documentos ya conocidos (spec 016)."""
import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import (
    COMPANY_FINDING_COLUMNS,
    ImportCompaniesFromExcel,
)
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_findings_writer import FakeFindingsWriter
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_not_linked_log_generator import FakeNotLinkedLogGenerator
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo

_UPDATE = {
    "NIT": "900111111", "Nombre en BD local": "EMPRESA VIEJA",
    "Nombre en Odoo": "EMPRESA NUEVA", "Acción": "Actualizada",
}


class RecordingLogger:
    def __init__(self):
        self.user_msgs = []

    def _rec(self, user_msg):
        if user_msg:
            self.user_msgs.append(user_msg)

    def info(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def warning(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def error(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)


def _found(nit, name):
    return NitResult(nit, True, name, "Odoo", "Odoo/NIT")


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "company_repo": FakeCompanyRepo(initial=[{"id": 1, "nit": "900111111", "name": "EMPRESA VIEJA"}]),
        "package_repo": FakePackageRepo([{"id": 10, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([{"id": 20, "name": "PROVEEDOR X"}]),
        "special_repo": FakeSpecialRepo([{"id": 30, "name": "ESPECIAL X"}]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(
            results=[_found("900111111", "EMPRESA NUEVA")], local_updates=[_UPDATE]
        ),
        "progress": FakeProgress(),
        "logger": RecordingLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
        "not_linked_log_generator": FakeNotLinkedLogGenerator(),
        "findings_writer": FakeFindingsWriter(),
    }


def _df(*nits):
    return pl.DataFrame({
        "NIT": list(nits),
        "RAZON SOCIAL": [f"EMPRESA {n}" for n in nits],
        "PAQUETE": ["PAQUETE BASICO"] * len(nits),
    })


def test_known_document_is_validated_against_odoo_and_updated(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_df("900111111"))

    assert deps["nit_service"].called_with == ["900111111"]  # el documento conocido también se consulta
    assert uc._findings["bd_local_actualizada"] == [_UPDATE]


def test_companies_created_counts_only_new_documents(deps):
    deps["nit_service"] = FakeNitService(
        results=[_found("900111111", "EMPRESA NUEVA"), _found("900999999", "EMPRESA NUEVA TRES")],
    )
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_df("900111111", "900999999"))

    assert uc._companies_created == 1
    names = {c["nit"]: c["name"] for c in deps["company_repo"].all()}
    assert names["900999999"] == "EMPRESA NUEVA TRES"


def test_rues_cache_comes_from_the_injected_loader(deps, tmp_path):
    cache = {"900333333": object()}
    seen = {}

    def loader(path):
        seen["path"] = path
        return cache

    uc = ImportCompaniesFromExcel(**deps, rues_cache_loader=loader)

    uc._progress_companies(_df("900111111"))

    assert seen["path"].endswith("data.json") and str(tmp_path) in seen["path"]
    assert deps["nit_service"].rues_cache is cache


def test_without_loader_the_search_gets_an_empty_cache(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_df("900111111"))

    assert deps["nit_service"].rues_cache == {}


def test_bd_local_actualizada_book_in_summary(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc.execute(_df("900111111"))

    writer = deps["findings_writer"]
    assert writer.books["bd_local_actualizada"] == [_UPDATE]
    assert COMPANY_FINDING_COLUMNS["bd_local_actualizada"] == [
        "NIT", "Nombre en BD local", "Nombre en Odoo", "Acción",
    ]
    assert len(deps["logger"].user_msgs) == 1                    # un solo resumen final
    assert "bd_local_actualizada=1" in deps["logger"].user_msgs[0]


def test_not_found_log_unchanged(deps):
    deps["nit_service"] = FakeNitService(results=[NitResult("900999999", False, None, "Odoo, RUES")])
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_df("900999999"))

    generator = deps["not_found_log_generator"]
    assert len(generator.calls) == 1
    rows, _ = generator.calls[0]
    assert [(r.nit, r.is_company, r.name) for r in rows] == [("900999999", False, "EMPRESA 900999999")]


def test_data_json_is_written_with_the_results_of_this_run(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_df("900111111"))

    written, path = deps["nit_service"]._written
    assert [r.nit for r in written] == ["900111111"] and path.endswith("data.json")
