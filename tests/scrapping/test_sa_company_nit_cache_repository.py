"""Tests para SaCompanyNitCacheRepository."""
import pytest

from src.scrapping.domain.exceptions import NitCacheSaveError
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


def test_save_many_failure_raises_nit_cache_save_error():
    class FailingCompanyRepo(FakeCompanyRepo):
        def save_batch(self, companies):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(FailingCompanyRepo(), logger=FakeLogger())

    with pytest.raises(NitCacheSaveError):
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


# ── Búsqueda por nombre (T10-T11) ────────────────────────────────────────────


def test_get_by_names_matches_normalized_name():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "830055408", "name": "CLINICA X SAS"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    result = repo.get_by_names(["Clínica X S.A.S."])

    assert result["Clínica X S.A.S."].name == "CLINICA X SAS"
    assert result["Clínica X S.A.S."].checked_bases == "BD local"
    assert result["Clínica X S.A.S."].source == "BD local/nombre"


def test_get_by_names_returns_empty_when_name_not_found():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.get_by_names(["OTRA EMPRESA"]) == {}


def test_get_by_names_ignores_blank_names():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.get_by_names(["", "   "]) == {}


def test_get_by_names_returns_empty_when_repo_fails():
    class FailingCompanyRepo(FakeCompanyRepo):
        def all(self):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(FailingCompanyRepo())

    assert repo.get_by_names(["EMPRESA UNO"]) == {}


def test_indexes_are_built_once_for_both_lookups():
    class CountingCompanyRepo(FakeCompanyRepo):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.all_calls = 0

        def all(self):
            self.all_calls += 1
            return super().all()

    company_repo = CountingCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    repo.get_many(["111"])
    repo.get_by_names(["EMPRESA UNO"])

    assert company_repo.all_calls == 1


def test_get_many_reports_source_by_nit():
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.get_many(["111"])["111"].source == "BD local/NIT"


# ── Reporte de omisiones al persistir (T12) ──────────────────────────────────


def test_save_many_returns_empty_when_all_persisted():
    company_repo = FakeCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.save_many([NitResult("111", True, "EMPRESA UNO")]) == []


def test_save_many_returns_nits_omitted_by_duplicate_name():
    """El nombre ya existe con otro NIT: save_batch lo descarta en silencio."""
    company_repo = FakeCompanyRepo(initial=[
        {"id": 1, "nit": "111", "name": "EMPRESA UNO"},
    ])
    repo = SaCompanyNitCacheRepository(company_repo)

    omitted = repo.save_many([NitResult("222", True, "EMPRESA UNO")])

    assert omitted == ["222"]


def test_save_many_returns_all_when_save_batch_fails():
    class FailingCompanyRepo(FakeCompanyRepo):
        def save_batch(self, companies):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(FailingCompanyRepo(), logger=FakeLogger())

    assert repo.save_many([NitResult("111", True, "EMPRESA UNO")]) == ["111"]


def test_save_many_returns_empty_when_nothing_to_persist():
    repo = SaCompanyNitCacheRepository(FakeCompanyRepo())

    assert repo.save_many([NitResult("111", False)]) == []


def test_fake_cache_repo_get_by_names_returns_results_keyed_by_name():
    from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo

    repo = FakeNitCacheRepo(
        cached_by_name={"EMPRESA UNO": NitResult("111", True, "EMPRESA UNO")}
    )

    result = repo.get_by_names(["EMPRESA UNO", "OTRA"])

    assert list(result) == ["EMPRESA UNO"]


def test_fake_cache_repo_save_many_reports_omitted():
    from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo

    repo = FakeNitCacheRepo(omit=["222"])

    assert repo.save_many([NitResult("222", True, "EMPRESA UNO")]) == ["222"]
