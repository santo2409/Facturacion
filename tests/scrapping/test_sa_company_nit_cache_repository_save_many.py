"""Spec 017, T01: save_many nunca envía el mismo NIT normalizado dos veces."""
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from tests.fakes.fake_company_repo import FakeCompanyRepo


class SpyCompanyRepo(FakeCompanyRepo):
    """Registra cada lote recibido por save_batch."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.received = []

    def save_batch(self, companies):
        self.received.append([(c.nit, c.name) for c in companies])
        return super().save_batch(companies)


def test_save_many_deduplica_por_nit_normalizado():
    company_repo = SpyCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    omitted = repo.save_many([
        NitResult("8001548370", True, "EXPERIENZA SAS", source="RUES/NIT"),
        NitResult("800154837", True, "EXPERIENZA S A S", source="Odoo/NIT"),
        NitResult("900111111", True, "OTRA EMPRESA", source="Odoo/NIT"),
    ])

    assert company_repo.received == [
        [("800154837", "EXPERIENZA S A S"), ("900111111", "OTRA EMPRESA")]
    ]
    assert omitted == []


def test_save_many_sin_fuente_odoo_conserva_el_primero():
    company_repo = SpyCompanyRepo()
    repo = SaCompanyNitCacheRepository(company_repo)

    repo.save_many([
        NitResult("8001548370", True, "EXPERIENZA SAS", source="RUES/NIT"),
        NitResult("800154837", True, "EXPERIENZA S A S", source="RUES/NIT"),
    ])

    assert company_repo.received == [[("800154837", "EXPERIENZA SAS")]]


def test_save_many_no_altera_los_resultados_del_llamador():
    repo = SaCompanyNitCacheRepository(SpyCompanyRepo())
    con_dv = NitResult("8001548370", True, "EXPERIENZA SAS", source="RUES/NIT")
    sin_dv = NitResult("800154837", True, "EXPERIENZA S A S", source="Odoo/NIT")
    results = [con_dv, sin_dv]

    repo.save_many(results)

    assert results == [con_dv, sin_dv]
    assert (con_dv.nit, con_dv.name) == ("8001548370", "EXPERIENZA SAS")
    assert (sin_dv.nit, sin_dv.name) == ("800154837", "EXPERIENZA S A S")
