"""Opción 2: Odoo como fuente de verdad también para las empresas ya conocidas (spec 016)."""
import polars as pl
import pytest

from src.billers.application.use_cases.import_billers_from_excel import (
    BILLER_FINDING_COLUMNS,
    ImportBillersFromExcel,
)
from src.company.domain.entities.company import Company
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_findings_writer import FakeFindingsWriter
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_progress import FakeProgress

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


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "biller_repo": FakeBillerRepo(),
        "company_repo": FakeCompanyRepo(initial=[
            {"id": 1, "nit": "900111111", "name": "EMPRESA VIEJA"},
            {"id": 2, "nit": "900222222", "name": "EMPRESA DOS"},
        ]),
        "biller_company_repo": FakeBillerCompanyRepo(),
        "nit_service": FakeNitService(
            results=[Company("900111111", "EMPRESA NUEVA"), Company("900222222", "EMPRESA DOS")],
            local_updates=[_UPDATE],
        ),
        "progress": FakeProgress(),
        "fuzz": FakeFuzz(),
        "logger": RecordingLogger(),
        "findings_writer": FakeFindingsWriter(),
    }


def _df(*nits):
    return pl.DataFrame({
        "NIT": list(nits),
        "GESTOR": ["ALFA"] * len(nits),
        "EMPRESA": [f"EMPRESA {n}" for n in nits],
    })


def test_known_nit_with_different_odoo_name_is_validated_and_updated(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111"))

    assert deps["nit_service"].called_with == ["900111111"]  # el NIT conocido también se consulta
    names = {c["nit"]: c["name"] for c in deps["company_repo"].all()}
    assert names["900111111"] == "EMPRESA NUEVA"


def test_nit_service_receives_all_nits_including_known_ones(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111", "900222222", "900333333"))

    assert deps["nit_service"].called_with == ["900111111", "900222222", "900333333"]


def test_rues_cache_is_loaded_from_data_json_and_passed_to_the_search(deps, tmp_path):
    cache = {"900333333": object()}
    seen = {}

    def loader(path):
        seen["path"] = path
        return cache

    uc = ImportBillersFromExcel(**deps, rues_cache_loader=loader)

    uc.execute(_df("900111111"))

    assert seen["path"].endswith("data.json") and str(tmp_path) in seen["path"]
    assert deps["nit_service"].rues_cache is cache


def test_without_rues_cache_loader_the_search_gets_an_empty_cache(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111"))

    assert deps["nit_service"].rues_cache == {}


def test_data_json_is_written_with_the_results_of_this_run(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111"))

    written, path = deps["nit_service"]._written
    assert [r.nit for r in written] == ["900111111", "900222222"]
    assert path.endswith("data.json")


def test_bd_local_actualizada_book_and_summary(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111"))

    assert deps["findings_writer"].books["bd_local_actualizada"] == [_UPDATE]
    assert deps["findings_writer"].columns["bd_local_actualizada"] == [
        "NIT", "Nombre en BD local", "Nombre en Odoo", "Acción",
    ]
    assert BILLER_FINDING_COLUMNS["bd_local_actualizada"][3] == "Acción"
    assert len(deps["logger"].user_msgs) == 1
    assert "bd_local_actualizada=1" in deps["logger"].user_msgs[0]


def test_no_updates_means_no_bd_local_actualizada_book(deps):
    deps["nit_service"] = FakeNitService(results=[Company("900111111", "EMPRESA VIEJA")])
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df("900111111"))

    assert "bd_local_actualizada" not in deps["findings_writer"].books
