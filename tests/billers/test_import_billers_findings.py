"""Hallazgos de la opción 2 en libros por ejecución (spec 011, RF-05/RF-08)."""
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


class RecordingLogger:
    """Doble local que registra `user_msg` (FakeLogger lo descarta)."""

    def __init__(self):
        self.user_msgs = []

    def _rec(self, msg, user_msg):
        if user_msg:
            self.user_msgs.append(user_msg)

    def info(self, msg, *, user_msg=None, **_):
        self._rec(msg, user_msg)

    def warning(self, msg, *, user_msg=None, **_):
        self._rec(msg, user_msg)

    def error(self, msg, *, user_msg=None, **_):
        self._rec(msg, user_msg)


class DropsOneCompanyRepo(FakeCompanyRepo):
    """No guarda la empresa 900999999: simula una empresa que no queda en la BD."""

    def save(self, company):
        if company.nit == "900999999":
            return None
        return super().save(company)


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "biller_repo": FakeBillerRepo(),
        "company_repo": DropsOneCompanyRepo(),
        "biller_company_repo": FakeBillerCompanyRepo(),
        "nit_service": FakeNitService(results=[
            Company("900111111", "EMPRESA A"),
            Company("900222222", "EMPRESA A"),   # mismo nombre que la anterior → vínculo duplicado
            Company("900333333", "EMPRESA C"),
            Company("900999999", "EMPRESA X"),
        ]),
        "progress": FakeProgress(),
        "fuzz": FakeFuzz(),
        "logger": RecordingLogger(),
        "findings_writer": FakeFindingsWriter(),
    }


def _df(rows):
    return pl.DataFrame({
        "NIT": [r[0] for r in rows],
        "GESTOR": [r[1] for r in rows],
        "EMPRESA": [r[2] for r in rows],
    })


_PROBLEM_ROWS = [
    ("900111111", "ALFA", "EMPRESA A"),
    ("900222222", "BETA", "EMPRESA A"),   # duplicada: misma empresa que 900111111
    ("900333333", "NAN", "EMPRESA C"),    # facturador inexistente
    ("900999999", "ALFA", "EMPRESA X"),   # empresa que no queda en la BD
]


def test_three_finding_books_with_their_columns(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df(_PROBLEM_ROWS))

    writer = deps["findings_writer"]
    assert writer.books == {
        "empresa_no_encontrada": [{"NIT": "900999999", "Facturador": "ALFA"}],
        "facturador_no_encontrado": [{"NIT": "900333333", "Facturador": "NAN"}],
        "vinculacion_duplicada": [{
            "NIT": "900111111", "Empresa": "EMPRESA A",
            "Facturador descartado": "ALFA", "Facturador vigente": "BETA",
        }],
    }
    assert writer.columns == BILLER_FINDING_COLUMNS
    assert BILLER_FINDING_COLUMNS == {
        "empresa_no_encontrada": ["NIT", "Facturador"],
        "facturador_no_encontrado": ["NIT", "Facturador"],
        "vinculacion_duplicada": ["NIT", "Empresa", "Facturador descartado", "Facturador vigente"],
        "bd_local_actualizada": ["NIT", "Nombre en BD local", "Nombre en Odoo", "Acción"],  # spec 016
    }


def test_duplicate_link_still_persists_last_biller(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df(_PROBLEM_ROWS[:2]))

    links = deps["biller_company_repo"].all()
    beta_id = next(b["id"] for b in deps["biller_repo"].all() if b["name"] == "BETA")
    assert len(links) == 1 and links[0]["biller"] == beta_id  # comportamiento actual: prevalece el último


def test_no_per_row_user_msg_and_single_summary(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df(_PROBLEM_ROWS))

    user_msgs = deps["logger"].user_msgs
    assert len(user_msgs) == 1
    assert "empresa_no_encontrada=1" in user_msgs[0]
    assert "facturador_no_encontrado=1" in user_msgs[0]
    assert "vinculacion_duplicada=1" in user_msgs[0]
    assert "fake" in user_msgs[0]  # ruta de la carpeta que devolvió el writer


def test_no_findings_no_folder(deps):
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([("900111111", "ALFA", "EMPRESA A"), ("900333333", "ALFA", "EMPRESA C")]))

    assert deps["findings_writer"].books == {}
    assert deps["logger"].user_msgs == ["Sin hallazgos."]


def test_findings_are_reset_between_executions(deps):
    uc = ImportBillersFromExcel(**deps)
    uc.execute(_df(_PROBLEM_ROWS))

    uc.execute(_df([("900111111", "ALFA", "EMPRESA A")]))

    assert deps["findings_writer"].books == {}
    assert deps["logger"].user_msgs[-1] == "Sin hallazgos."


def test_private_methods_work_without_execute(deps):
    uc = ImportBillersFromExcel(**deps)

    uc._process_billers(_df(_PROBLEM_ROWS))
    uc._process_companies(_df(_PROBLEM_ROWS))

    assert len(uc._findings["empresa_no_encontrada"]) == 1


# ── spec 015: vinculación duplicada = reemplazo (prevalece la última) ─────

def _same_company_nit_service(*nits):
    return FakeNitService(results=[Company(nit, "EMPRESA A") for nit in nits])


def test_duplicate_book_shows_discarded_and_current_biller(deps):
    deps["nit_service"] = _same_company_nit_service("900111111", "900222222")
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([("900111111", "ALFA", "EMPRESA A"), ("900222222", "BETA", "EMPRESA A")]))

    assert deps["findings_writer"].books["vinculacion_duplicada"] == [{
        "NIT": "900111111", "Empresa": "EMPRESA A",
        "Facturador descartado": "ALFA", "Facturador vigente": "BETA",
    }]


def test_chain_of_replacements_reports_each_step(deps):
    deps["nit_service"] = _same_company_nit_service("900111111", "900222222", "900444444")
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([
        ("900111111", "ALFA", "EMPRESA A"),
        ("900222222", "BETA", "EMPRESA A"),
        ("900444444", "GAMA", "EMPRESA A"),
    ]))

    rows = deps["findings_writer"].books["vinculacion_duplicada"]
    assert [(r["Facturador descartado"], r["Facturador vigente"]) for r in rows] == [
        ("ALFA", "BETA"), ("BETA", "GAMA"),
    ]
    links = deps["biller_company_repo"].all()
    gama_id = next(b["id"] for b in deps["biller_repo"].all() if b["name"] == "GAMA")
    assert len(links) == 1 and links[0]["biller"] == gama_id  # prevalece la última


def test_same_biller_repeated_is_not_a_conflict(deps):
    deps["nit_service"] = _same_company_nit_service("900111111", "900222222")
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([("900111111", "ALFA", "EMPRESA A"), ("900222222", "ALFA", "EMPRESA A")]))

    assert "vinculacion_duplicada" not in deps["findings_writer"].books
    alfa_id = next(b["id"] for b in deps["biller_repo"].all() if b["name"] == "ALFA")
    assert [l["biller"] for l in deps["biller_company_repo"].all()] == [alfa_id]


def test_console_summary_counts_replacements(deps):
    deps["nit_service"] = _same_company_nit_service("900111111", "900222222", "900444444")
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([
        ("900111111", "ALFA", "EMPRESA A"),
        ("900222222", "BETA", "EMPRESA A"),
        ("900444444", "GAMA", "EMPRESA A"),
    ]))

    assert "vinculacion_duplicada=2" in deps["logger"].user_msgs[-1]


class TechnicalLogger(RecordingLogger):
    """Registra también el mensaje técnico (RecordingLogger solo guarda user_msg)."""

    def __init__(self):
        super().__init__()
        self.errors = []

    def error(self, msg, *, user_msg=None, **_):
        self.errors.append(msg)
        self._rec(msg, user_msg)


def test_technical_log_says_replaced_not_omitted(deps):
    deps["nit_service"] = _same_company_nit_service("900111111", "900222222")
    deps["logger"] = TechnicalLogger()
    uc = ImportBillersFromExcel(**deps)

    uc.execute(_df([("900111111", "ALFA", "EMPRESA A"), ("900222222", "BETA", "EMPRESA A")]))

    text = "\n".join(deps["logger"].errors)
    assert "reemplazada" in text and "reemplazado" in text
    assert "ALFA" in text and "BETA" in text
    assert "omitida" not in text
    assert deps["logger"].user_msgs[-1].startswith("Hallazgos")  # sin user_msg por fila (spec 011)
