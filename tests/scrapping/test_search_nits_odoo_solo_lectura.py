"""Spec 017, T06 (AC-09): el guardado en lote nunca escribe en Odoo."""
import pytest

from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo

_CLIENTS = {
    "800148514": {"id": 1, "name": "SKANDIA ADMINISTRADORA"},
    "800154837": {"id": 2, "name": "EXPERIENZA SAS"},
    "111111111": {"id": 3, "name": "EMPRESA UNO"},
}


class _NoScraper:
    def search_nits(self, nits, show_progress=False):
        return [NitResult(n, False) for n in nits]


class _StrictCompanyRepo(FakeCompanyRepo):
    def save_batch(self, companies):
        nits = [c.nit for c in companies]
        if len(nits) != len(set(nits)):
            raise RuntimeError("cannot affect row a second time")
        return super().save_batch(companies)


def _run(cache, odoo):
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(_NoScraper()), odoo_repo=odoo, nit_cache_repo=cache, logger=FakeLogger()
    )
    return uc.execute(["800148514", "8001548370", "800154837", "111111111", "999999999"])


@pytest.mark.parametrize("escenario", ["guardado_ok_con_nit_repetido", "conflicto_real", "fallo_de_guardado"])
def test_guardado_en_lote_no_escribe_en_odoo(escenario):
    odoo = FakeOdooRepo(clients=dict(_CLIENTS))
    if escenario == "guardado_ok_con_nit_repetido":
        cache = SaCompanyNitCacheRepository(_StrictCompanyRepo(), logger=FakeLogger())
    elif escenario == "conflicto_real":
        cache = SaCompanyNitCacheRepository(
            _StrictCompanyRepo(initial=[{"id": 9, "nit": "555555555", "name": "EMPRESA UNO"}]),
            logger=FakeLogger(),
        )
    else:
        cache = FakeNitCacheRepo(fail=True)

    _run(cache, odoo)

    assert odoo.write_attempts == []
    assert set(odoo._clients) == set(_CLIENTS)
