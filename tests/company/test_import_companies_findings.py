"""Hallazgos de la opción 5 en libros por ejecución (spec 011, RF-06/RF-08/RF-09)."""
import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import (
    COMPANY_FINDING_COLUMNS,
    ImportCompaniesFromExcel,
)
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


class RecordingLogger:
    """Doble local que registra `user_msg` (FakeLogger lo descarta)."""

    def __init__(self):
        self.user_msgs = []
        self.infos = []

    def _rec(self, user_msg):
        if user_msg:
            self.user_msgs.append(user_msg)

    def info(self, msg, *, user_msg=None, **_):
        self.infos.append(msg)
        self._rec(user_msg)

    def warning(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def error(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "company_repo": FakeCompanyRepo(initial=[
            {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
            {"id": 2, "nit": "900222222", "name": "EMPRESA B"},
        ]),
        "package_repo": FakePackageRepo([
            {"id": 10, "name": "PAQUETE BASICO"},
            {"id": 11, "name": "PAQUETE DOS"},
        ]),
        # catálogos con datos: un catálogo vacío emite su propio aviso (spec 007), ajeno a esta spec
        "provider_repo": FakeProviderRepo([{"id": 20, "name": "PROVEEDOR X"}]),
        "special_repo": FakeSpecialRepo([{"id": 30, "name": "ESPECIAL X"}]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(results=[]),
        "progress": FakeProgress(),
        "logger": RecordingLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
        "not_linked_log_generator": FakeNotLinkedLogGenerator(),
        "findings_writer": FakeFindingsWriter(),
    }


_PROBLEM_DF = pl.DataFrame({
    "NIT": ["9001111115", "900111111", "900222222", "900999999"],
    "RAZON SOCIAL": ["EMPRESA A", "EMPRESA A", "EMPRESA B", "EMPRESA FANTASMA"],
    "PAQUETE": ["PAQUETE BASICO", "PAQUETE DOS", "NO EXISTE", "PAQUETE BASICO"],
})

_CLEAN_DF = pl.DataFrame({
    "NIT": ["900111111", "900222222"],
    "RAZON SOCIAL": ["EMPRESA A", "EMPRESA B"],
    "PAQUETE": ["PAQUETE BASICO", "PAQUETE DOS"],
})


def test_three_finding_books_and_unlinked_company_only_in_empresas_no_vinculadas(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc.execute(_PROBLEM_DF)

    writer = deps["findings_writer"]
    assert writer.books == {
        "documento_acotado": [
            {"Documento original": "9001111115", "Documento acotado": "900111111"}
        ],
        "paquetes_en_conflicto": [
            {"Documento": "900111111", "Paquete descartado": "PAQUETE BASICO", "Paquete vigente": "PAQUETE DOS"}
        ],
        "paquete_no_encontrado": [
            {"Documento": "900222222", "Razón social": "EMPRESA B", "Paquete": "NO EXISTE"}
        ],
    }
    assert writer.columns == COMPANY_FINDING_COLUMNS
    assert "empresa_no_encontrada" not in writer.columns


def test_empresas_no_vinculadas_unchanged(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc.execute(_PROBLEM_DF)

    generator = deps["not_linked_log_generator"]
    assert len(generator.calls) == 1
    rows, output_dir = generator.calls[0]
    assert [(r.document, r.company_name, r.package, r.reason) for r in rows] == [
        ("900999999", "EMPRESA FANTASMA", "PAQUETE BASICO", "Empresa no encontrada en la base de datos")
    ]
    assert output_dir == deps["logs_dir"]


def test_private_methods_work_without_execute(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc._progress_companies(_PROBLEM_DF)
    uc._progress_companies_to_packages(_PROBLEM_DF)

    assert len(uc._findings["documento_acotado"]) == 1
    assert len(uc._findings["paquete_no_encontrado"]) == 1


def test_no_per_row_user_msg_and_single_summary(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc.execute(_PROBLEM_DF)

    user_msgs = deps["logger"].user_msgs
    assert len(user_msgs) == 1                       # sin mensajes por fila
    assert len(deps["logger"].infos) == 1            # un solo info por ejecución
    summary = user_msgs[0]
    assert "Empresas creadas:" in summary and "Filas sin vincular: 1" in summary
    for expected in ("documento_acotado=1", "paquetes_en_conflicto=1", "paquete_no_encontrado=1", "fake"):
        assert expected in summary


def test_no_findings_no_folder_and_summary_says_sin_hallazgos(deps):
    uc = ImportCompaniesFromExcel(**deps)

    uc.execute(_CLEAN_DF)

    assert deps["findings_writer"].books == {}
    assert deps["logger"].user_msgs[-1].endswith("Sin hallazgos.")


def test_findings_are_reset_between_executions(deps):
    uc = ImportCompaniesFromExcel(**deps)
    uc.execute(_PROBLEM_DF)

    uc.execute(_CLEAN_DF)

    assert deps["findings_writer"].books == {}
