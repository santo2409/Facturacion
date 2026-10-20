"""Spec 017, T04: SKANDIA no es duplicado y el conflicto real se conserva."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    ACTION_NOT_UPDATED,
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_odoo_repo import FakeOdooRepo


class _NoScraper:
    def search_nits(self, nits, show_progress=False):
        return [NitResult(n, False) for n in nits]


class StrictCompanyRepo(FakeCompanyRepo):
    """Como Postgres: un NIT repetido dentro del mismo INSERT hace fallar todo el lote."""

    def save_batch(self, companies):
        nits = [c.nit for c in companies]
        if len(nits) != len(set(nits)):
            raise RuntimeError("ON CONFLICT DO UPDATE command cannot affect row a second time")
        return super().save_batch(companies)


def _use_case(company_repo, odoo_clients):
    cache = SaCompanyNitCacheRepository(company_repo, logger=FakeLogger())
    return SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(_NoScraper()),
        odoo_repo=FakeOdooRepo(clients=odoo_clients),
        nit_cache_repo=cache,
        logger=FakeLogger(),
    )


def test_skandia_dos_nit_no_marcan_conflicto():
    company_repo = StrictCompanyRepo(initial=[
        {"id": 583, "nit": "800148514", "name": "SKANDIA PENSIONES Y CESANTÍAS"},
        {"id": 662, "nit": "800184549", "name": "SKANDIA PENSIONES Y CESANTÍAS S.A."},
    ])
    uc = _use_case(company_repo, {
        "800148514": {"id": 78932, "name": "SKANDIA ADMINISTRADORA DE FONDOS DE PENSIONES Y CESANTIAS S.A."},
        "800184549": {"id": 85863, "name": "SKANDIA FONDO DE CESANTIAS"},
        "800154837": {"id": 1, "name": "EXPERIENZA SAS"},
    })

    # Incluye el mismo NIT con y sin DV: antes hacía fallar todo el lote.
    results = uc.execute(["800148514", "800184549", "8001548370", "800154837"])

    assert all(r.conflict == "" and r.save_error == "" for r in results)
    names = {c["nit"]: c["name"] for c in company_repo.all()}
    assert names["800148514"] == "SKANDIA ADMINISTRADORA DE FONDOS DE PENSIONES Y CESANTIAS S.A."
    assert names["800184549"] == "SKANDIA FONDO DE CESANTIAS"
    assert names["800154837"] == "EXPERIENZA SAS"


def test_conflicto_real_solo_marca_el_nit_omitido():
    company_repo = StrictCompanyRepo(initial=[
        {"id": 1, "nit": "999999999", "name": "EMPRESA UNO"},
    ])
    uc = _use_case(company_repo, {
        "111111111": {"id": 1, "name": "EMPRESA UNO"},
        "222222222": {"id": 2, "name": "EMPRESA DOS"},
    })

    results = {str(r.nit): r for r in uc.execute(["111111111", "222222222"])}

    assert results["111111111"].conflict and results["111111111"].save_error == ""
    assert results["222222222"].conflict == "" and results["222222222"].save_error == ""
    assert {c["nit"] for c in company_repo.all()} == {"999999999", "222222222"}
    acciones = {u["NIT"]: u["Acción"] for u in uc.local_updates}
    assert acciones["111111111"] == ACTION_NOT_UPDATED
