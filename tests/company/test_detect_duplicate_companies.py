from pathlib import Path

from src.company.application.use_cases.detect_duplicate_companies import (
    DetectDuplicateCompanies,
)
from src.company.domain.services.duplicate_company_detector import DuplicateCompanyDetector
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_duplicate_log_generator import FakeDuplicateLogGenerator
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_progress import FakeProgress


def build(company_repo=None, generator=None):
    return DetectDuplicateCompanies(
        company_repo=company_repo or FakeCompanyRepo(),
        detector=DuplicateCompanyDetector(FakeFuzz()),
        log_generator=generator or FakeDuplicateLogGenerator(),
        progress=FakeProgress(),
        logger=FakeLogger(),
    )


def test_execute_reads_companies_and_calls_generator_with_candidates(tmp_path):
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "LAB3 SAS"},
        {"id": 2, "nit": "222", "name": "LAB3 S.A.S"},
    ])
    generator = FakeDuplicateLogGenerator()
    uc = build(company_repo=company_repo, generator=generator)

    uc.execute(tmp_path)

    assert len(generator.calls) == 1
    candidates, output_dir = generator.calls[0]
    assert len(candidates) == 1
    assert output_dir == tmp_path


def test_execute_returns_generated_path(tmp_path):
    generator = FakeDuplicateLogGenerator()
    uc = build(generator=generator)

    result = uc.execute(tmp_path)

    assert result == tmp_path / "empresas_duplicadas.xlsx"


def test_execute_with_no_companies_generates_empty_report(tmp_path):
    generator = FakeDuplicateLogGenerator()
    uc = build(company_repo=FakeCompanyRepo(), generator=generator)

    uc.execute(tmp_path)

    candidates, _ = generator.calls[0]
    assert candidates == []


def test_execute_handles_repo_returning_none(tmp_path):
    class NoneCompanyRepo(FakeCompanyRepo):
        def all(self):
            return None

    generator = FakeDuplicateLogGenerator()
    uc = build(company_repo=NoneCompanyRepo(), generator=generator)

    uc.execute(tmp_path)

    candidates, _ = generator.calls[0]
    assert candidates == []


def test_execute_never_writes_to_company_repo(tmp_path):
    class NoWriteCompanyRepo(FakeCompanyRepo):
        def save(self, company):
            raise AssertionError("execute() no debe escribir en companies")

        def save_batch(self, companies):
            raise AssertionError("execute() no debe escribir en companies")

    company_repo = NoWriteCompanyRepo(initial=[{"id": 1, "nit": "111", "name": "EMPRESA A"}])
    uc = build(company_repo=company_repo)

    uc.execute(tmp_path)  # no debe lanzar AssertionError
