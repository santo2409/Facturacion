"""Spec 017, T02: un fallo de guardado se distingue de 'nada que guardar'."""
import pytest

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.exceptions import NitCacheSaveError
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo


class NoneReturningCompanyRepo(FakeCompanyRepo):
    """Imita SaCompanyRepository.save_batch tras un rollback: devuelve None."""

    def save_batch(self, companies):
        return None


def test_save_many_lanza_si_falla_save_batch():
    repo = SaCompanyNitCacheRepository(NoneReturningCompanyRepo(), logger=FakeLogger())

    with pytest.raises(NitCacheSaveError):
        repo.save_many([NitResult("111", True, "EMPRESA UNO")])


def test_save_many_lanza_si_save_batch_lanza_excepcion():
    class RaisingCompanyRepo(FakeCompanyRepo):
        def save_batch(self, companies):
            raise ConnectionError("BD no disponible")

    repo = SaCompanyNitCacheRepository(RaisingCompanyRepo(), logger=FakeLogger())

    with pytest.raises(NitCacheSaveError):
        repo.save_many([NitResult("111", True, "EMPRESA UNO")])


def test_save_many_lote_vacio_no_es_error():
    repo = SaCompanyNitCacheRepository(NoneReturningCompanyRepo())

    assert repo.save_many([NitResult("111", False)]) == []


def test_save_many_todo_filtrado_por_nombre_no_es_error():
    company_repo = FakeCompanyRepo(initial=[{"id": 1, "nit": "111", "name": "EMPRESA UNO"}])
    repo = SaCompanyNitCacheRepository(company_repo)

    assert repo.save_many([NitResult("222", True, "EMPRESA UNO")]) == ["222"]


def test_fake_cache_repo_fail_lanza_nit_cache_save_error():
    repo = FakeNitCacheRepo(fail=True)

    with pytest.raises(NitCacheSaveError):
        repo.save_many([NitResult("111", True, "EMPRESA UNO")])
