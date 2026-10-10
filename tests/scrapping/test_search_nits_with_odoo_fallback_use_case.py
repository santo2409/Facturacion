"""Tests para SearchNitsWithOdooFallbackUseCase."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo


class TrackingScraper:
    def __init__(self, results_by_nit=None):
        self._results_by_nit = results_by_nit or {}
        self.called_with = None

    def search_nits(self, nits, show_progress=False):
        self.called_with = list(nits)
        return [self._results_by_nit.get(nit, NitResult(nit, False)) for nit in nits]


def test_odoo_resolves_all_nits_scraper_never_called():
    scraper = TrackingScraper()
    odoo = FakeOdooRepo(clients={
        "111": {"id": 1, "name": "EMPRESA UNO"},
        "222": {"id": 2, "name": "EMPRESA DOS"},
    })
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["111", "222"])

    assert scraper.called_with is None
    assert [r.name for r in result] == ["EMPRESA UNO", "EMPRESA DOS"]
    assert all(r.is_company for r in result)


def test_odoo_resolves_subset_rues_called_only_with_pending():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["111", "222"])

    assert scraper.called_with == ["222"]
    assert result[0].name == "EMPRESA ODOO"
    assert result[1].name == "EMPRESA RUES"


def test_without_odoo_repo_delegates_fully_to_rues():
    scraper = TrackingScraper(results_by_nit={"111": NitResult("111", True, "EMPRESA RUES")})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=None)

    result = uc.execute(["111"])

    assert scraper.called_with == ["111"]
    assert result[0].name == "EMPRESA RUES"


def test_connect_failure_degrades_to_full_rues_without_raising():
    class FailingOdooRepo(FakeOdooRepo):
        def connect(self):
            raise ConnectionError("Autenticación fallida")

    scraper = TrackingScraper(results_by_nit={"111": NitResult("111", True, "EMPRESA RUES")})
    logger = FakeLogger()
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=FailingOdooRepo(), logger=logger
    )

    result = uc.execute(["111"])

    assert scraper.called_with == ["111"]
    assert result[0].name == "EMPRESA RUES"
    assert logger.warnings


def test_preserves_input_order_across_sources():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = FakeOdooRepo(clients={
        "111": {"id": 1, "name": "EMPRESA ODOO 1"},
        "333": {"id": 3, "name": "EMPRESA ODOO 3"},
    })
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["111", "222", "333"])

    assert [r.nit for r in result] == ["111", "222", "333"]
    assert [r.name for r in result] == ["EMPRESA ODOO 1", "EMPRESA RUES", "EMPRESA ODOO 3"]


def test_nit_not_found_anywhere_stays_documented_as_not_company():
    scraper = TrackingScraper()  # sin resultados configurados -> NitResult(nit, False) por defecto
    odoo = FakeOdooRepo(clients={})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["999"])

    assert len(result) == 1
    assert result[0].nit == "999"
    assert result[0].is_company is False


class TrackingOdooRepo(FakeOdooRepo):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_calls = 0
        self.called_with = []

    def find_clients_batch(self, nits):
        self.batch_calls += 1
        self.called_with.extend(nits)
        return super().find_clients_batch(nits)


def test_nit_with_more_than_9_digits_is_normalized_before_odoo_query():
    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={"900123456": {"id": 1, "name": "EMPRESA ODOO"}})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["900.123.456-999"])

    assert odoo.called_with == ["900123456"]
    assert scraper.called_with is None
    assert result[0].nit == "900.123.456-999"
    assert result[0].name == "EMPRESA ODOO"
    assert result[0].is_company is True


def test_odoo_batch_called_once_for_all_pending_nits():
    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    uc.execute(["111", "222", "333"])

    assert odoo.batch_calls == 1
    assert sorted(odoo.called_with) == ["111", "222", "333"]


def test_odoo_batch_failure_degrades_to_full_rues_for_all_pending():
    class FailingBatchOdooRepo(FakeOdooRepo):
        def find_clients_batch(self, nits):
            raise ConnectionError("Timeout de red")

    scraper = TrackingScraper(results_by_nit={
        "111": NitResult("111", True, "EMPRESA RUES 1"),
        "222": NitResult("222", True, "EMPRESA RUES 2"),
    })
    logger = FakeLogger()
    odoo = FailingBatchOdooRepo(clients={"111": {"id": 1, "name": "NUNCA SE USA"}})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo, logger=logger)

    result = uc.execute(["111", "222"])

    assert sorted(scraper.called_with) == ["111", "222"]
    assert [r.name for r in result] == ["EMPRESA RUES 1", "EMPRESA RUES 2"]
    assert logger.warnings


def test_checked_bases_is_odoo_only_when_resolved_there():
    scraper = TrackingScraper()
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA UNO"}})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["111"])

    assert result[0].checked_bases == "Odoo"


def test_checked_bases_is_odoo_and_rues_when_odoo_misses_but_rues_finds():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = FakeOdooRepo(clients={})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["222"])

    assert result[0].checked_bases == "Odoo, RUES"


def test_checked_bases_is_odoo_and_rues_when_not_found_anywhere():
    scraper = TrackingScraper()
    odoo = FakeOdooRepo(clients={})
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=odoo)

    result = uc.execute(["999"])

    assert result[0].is_company is False
    assert result[0].checked_bases == "Odoo, RUES"


def test_checked_bases_is_rues_only_without_odoo_repo():
    scraper = TrackingScraper()
    uc = SearchNitsWithOdooFallbackUseCase(SearchNitsUseCase(scraper), odoo_repo=None)

    result = uc.execute(["999"])

    assert result[0].checked_bases == "RUES"


def test_cache_hit_skips_rues_when_odoo_has_no_data():
    # spec 016: Odoo se consulta primero (una llamada); la BD local evita RUES
    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={})
    cache = FakeNitCacheRepo(cached={"111": NitResult("111", True, "EMPRESA CACHEADA", "BD local")})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    result = uc.execute(["111"])

    assert scraper.called_with is None
    assert odoo.batch_calls == 1
    assert result[0].name == "EMPRESA CACHEADA"
    assert result[0].checked_bases == "BD local"


def test_cache_miss_falls_back_to_odoo_then_rues():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = TrackingOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    result = uc.execute(["111", "222"])

    assert sorted(odoo.called_with) == ["111", "222"]
    assert scraper.called_with == ["222"]
    assert result[0].name == "EMPRESA ODOO"
    assert result[1].name == "EMPRESA RUES"


def test_new_positive_results_are_saved_to_cache():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = TrackingOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    uc.execute(["111", "222"])

    saved_names = sorted(r.name for r in cache.saved)
    assert saved_names == ["EMPRESA ODOO", "EMPRESA RUES"]


def test_negative_results_are_not_saved_to_cache():
    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={})
    cache = FakeNitCacheRepo(cached={})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    uc.execute(["999"])

    assert cache.saved == []


def test_already_cached_results_are_not_saved_again():
    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={})
    cache = FakeNitCacheRepo(cached={"111": NitResult("111", True, "EMPRESA CACHEADA", "BD local")})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    uc.execute(["111"])

    assert cache.saved == []


def test_not_found_uses_book_name_for_display_but_not_is_company():
    scraper = TrackingScraper()
    odoo = FakeOdooRepo(clients={})
    cache = FakeNitCacheRepo(cached={})
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=cache
    )

    result = uc.execute(["999"], book_names={"999": "EMPRESA DEL LIBRO"})

    assert result[0].name == "EMPRESA DEL LIBRO"
    assert result[0].is_company is False
    assert cache.saved == []


def test_cache_failure_degrades_gracefully_to_odoo_rues():
    class FailingNitCacheRepo(FakeNitCacheRepo):
        def get_many(self, nits):
            raise ConnectionError("BD no disponible")

    scraper = TrackingScraper()
    odoo = TrackingOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    logger = FakeLogger()
    uc = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper), odoo_repo=odoo, nit_cache_repo=FailingNitCacheRepo(), logger=logger
    )

    result = uc.execute(["111"])

    assert result[0].name == "EMPRESA ODOO"
    assert logger.warnings
