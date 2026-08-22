"""Tests para SaCompanyNitCacheRepository."""
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_logger import FakeLogger


def test_get_many_returns_only_requested_nits_found_in_db():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
        {"id": 2, "nit": "222", "name": "EMPRESA DOS"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    result = repo.get_many(["111", "999"])

    assert set(result.keys()) == {"111"}
    assert result["111"].name == "EMPRESA UNO"
    assert result["111"].checked_bases == "BD local"


def test_get_many_returns_empty_dict_when_table_is_empty():
    company_repo = FakeCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.get_many(["111"]) == {}


def test_get_many_returns_empty_dict_when_repo_fails():
    class FailingCompanyRepo(FakeCompanyRepo):
        def all(self):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(FailingCompanyRepo())

    assert repo.get_many(["111"]) == {}


def test_save_many_persists_only_positive_results_with_name():
    company_repo = FakeCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    repo.save_many([
        NitResult("111", True, "EMPRESA UNO"),
        NitResult("222", False),
        NitResult("333", True, None),
    ])

    nits = [c["nit"] for c in company_repo.all()]
    assert nits == ["111"]


def test_save_many_failure_does_not_raise():
    class FailingCompanyRepo(FakeCompanyRepo):
        def save_batch(self, companies):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(FailingCompanyRepo(), logger=FakeLogger())

    repo.save_many([NitResult("111", True, "EMPRESA UNO")])


def test_save_many_truncates_nit_to_9_digits_before_persisting():
    company_repo = FakeCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    repo.save_many([NitResult("8300554089", True, "EMPRESA CON DV")])

    nits = [c["nit"] for c in company_repo.all()]
    assert nits == ["830055408"]


def test_save_many_updates_existing_company_instead_of_duplicating():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "830055408", "name": "EMPRESA ORIGINAL"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    repo.save_many([NitResult("8300554089", True, "EMPRESA ACTUALIZADA")])

    companies = company_repo.all()
    assert len(companies) == 1
    assert companies[0]["nit"] == "830055408"
    assert companies[0]["name"] == "EMPRESA ACTUALIZADA"


def test_get_many_matches_db_nit_against_raw_nit_with_verification_digit():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "830055408", "name": "EMPRESA YA CACHEADA"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    result = repo.get_many(["8300554089"])

    assert set(result.keys()) == {"8300554089"}
    assert result["8300554089"].name == "EMPRESA YA CACHEADA"
