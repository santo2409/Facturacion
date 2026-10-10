"""Odoo es la fuente de verdad: el buscador de empresas lo consulta primero y
la BD local queda como respaldo (spec 016, RF-01 y RF-07)."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo


class TrackingScraper:
    def __init__(self, results_by_nit=None):
        self._results_by_nit = results_by_nit or {}
        self.called_with = None

    def search_nits(self, nits, show_progress=False):
        self.called_with = list(nits)
        return [self._results_by_nit.get(nit, NitResult(nit, False)) for nit in nits]


class RecordingLogger:
    """Doble local que registra `user_msg` (FakeLogger lo descarta)."""

    def __init__(self):
        self.user_msgs = []
        self.warnings = []

    def _rec(self, user_msg):
        if user_msg:
            self.user_msgs.append(user_msg)

    def info(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def warning(self, msg, *, user_msg=None, **_):
        self.warnings.append(msg)
        self._rec(user_msg)

    def error(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)


class BatchCountingOdooRepo(FakeOdooRepo):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.batch_calls = []

    def find_clients_batch(self, nits):
        self.batch_calls.append(list(nits))
        return super().find_clients_batch(nits)


def _cached(nit, name):
    return NitResult(nit, True, name, "BD local", "BD local/NIT")


def _use_case(odoo=None, cache=None, scraper=None, logger=None):
    return SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper or TrackingScraper()),
        odoo_repo=odoo,
        nit_cache_repo=cache,
        logger=logger or RecordingLogger(),
    )


def test_odoo_name_wins_over_local_name_for_known_nit():
    scraper = TrackingScraper()
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA NUEVA"}})
    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA VIEJA")})

    result = _use_case(odoo, cache, scraper).execute(["111"])

    assert result[0].name == "EMPRESA NUEVA"
    assert result[0].source == "Odoo/NIT"
    assert scraper.called_with is None


def test_local_fallback_when_odoo_has_no_data_and_rues_is_not_called():
    scraper = TrackingScraper()
    cache = FakeNitCacheRepo(cached={"222": _cached("222", "EMPRESA LOCAL")})

    result = _use_case(FakeOdooRepo(), cache, scraper).execute(["222"])

    assert result[0].name == "EMPRESA LOCAL"
    assert result[0].source == "BD local/NIT"
    assert scraper.called_with is None


def test_odoo_connect_failure_falls_back_to_local_and_rues_with_user_msg():
    class FailingConnect(FakeOdooRepo):
        def connect(self):
            raise ConnectionError("sin red")

    scraper = TrackingScraper(results_by_nit={"333": NitResult("333", True, "EMPRESA RUES")})
    cache = FakeNitCacheRepo(cached={"222": _cached("222", "EMPRESA LOCAL")})
    logger = RecordingLogger()
    uc = _use_case(FailingConnect(), cache, scraper, logger)

    result = uc.execute(["222", "333"])

    assert [r.name for r in result] == ["EMPRESA LOCAL", "EMPRESA RUES"]
    assert scraper.called_with == ["333"]
    assert uc.odoo_available is False
    assert logger.user_msgs == ["Odoo no disponible: se validó con la BD local y RUES."]


def test_odoo_batch_failure_falls_back_with_user_msg():
    class FailingBatch(FakeOdooRepo):
        def find_clients_batch(self, nits):
            raise RuntimeError("odoo caído")

    cache = FakeNitCacheRepo(cached={"222": _cached("222", "EMPRESA LOCAL")})
    logger = RecordingLogger()
    uc = _use_case(FailingBatch(), cache, logger=logger)

    result = uc.execute(["222"])

    assert result[0].name == "EMPRESA LOCAL"
    assert uc.odoo_available is False
    assert logger.user_msgs == ["Odoo no disponible: se validó con la BD local y RUES."]
    assert any("odoo caído" in w for w in logger.warnings)


def test_odoo_available_is_true_when_everything_works_and_no_user_msg():
    logger = RecordingLogger()
    uc = _use_case(FakeOdooRepo(clients={"111": {"id": 1, "name": "A"}}), logger=logger)

    uc.execute(["111"])

    assert uc.odoo_available is True
    assert logger.user_msgs == []


def test_known_nits_are_still_sent_to_odoo_in_a_single_batch():
    nits = [str(100000000 + i) for i in range(1200)]
    cache = FakeNitCacheRepo(cached={n: _cached(n, f"LOCAL {n}") for n in nits})
    odoo = BatchCountingOdooRepo(clients={n: {"id": i, "name": f"ODOO {n}"} for i, n in enumerate(nits)})

    result = _use_case(odoo, cache).execute(nits)

    assert len(odoo.batch_calls) == 1 and len(odoo.batch_calls[0]) == 1200
    assert result[0].name == f"ODOO {nits[0]}"


def test_odoo_calls_are_read_only():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "A"}})
    cache = FakeNitCacheRepo(cached={"222": _cached("222", "B")})

    _use_case(odoo, cache).execute(["111", "222", "333"])

    assert odoo.write_attempts == []


# ── T03: rues_cache (data.json solo ahorra RUES) ──────────────────────────

def _rues(nit, name):
    return NitResult(nit, True, name, "Odoo, RUES", "RUES/NIT")


def test_rues_cache_entry_avoids_scraping_that_nit():
    scraper = TrackingScraper()

    result = _use_case(FakeOdooRepo(), scraper=scraper).execute(
        ["333"], rues_cache={"333": _rues("333", "EMPRESA RUES CACHEADA")}
    )

    assert scraper.called_with is None
    assert result[0].name == "EMPRESA RUES CACHEADA"
    assert result[0].source == "RUES/NIT"
    assert result[0].is_company is True


def test_rues_cache_does_not_override_odoo_result():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "ODOO ACTUAL"}})

    result = _use_case(odoo).execute(["111"], rues_cache={"111": _rues("111", "RUES VIEJO")})

    assert result[0].name == "ODOO ACTUAL"
    assert result[0].source == "Odoo/NIT"


def test_only_uncached_nits_reach_the_scraper():
    scraper = TrackingScraper(results_by_nit={"444": NitResult("444", True, "EMPRESA RUES NUEVA")})

    result = _use_case(FakeOdooRepo(), scraper=scraper).execute(
        ["333", "444"], rues_cache={"333": _rues("333", "EMPRESA CACHEADA")}
    )

    assert scraper.called_with == ["444"]
    assert [r.name for r in result] == ["EMPRESA CACHEADA", "EMPRESA RUES NUEVA"]


def test_execute_without_rues_cache_behaves_as_before():
    scraper = TrackingScraper(results_by_nit={"333": NitResult("333", True, "EMPRESA RUES")})

    result = _use_case(FakeOdooRepo(), scraper=scraper).execute(["333"])

    assert scraper.called_with == ["333"]
    assert result[0].name == "EMPRESA RUES"


def test_rues_cache_entry_that_is_not_a_company_does_not_resolve():
    scraper = TrackingScraper()
    not_company = NitResult("333", False, None, "Odoo, RUES", "RUES/NIT")

    _use_case(FakeOdooRepo(), scraper=scraper).execute(["333"], rues_cache={"333": not_company})

    assert scraper.called_with == ["333"]  # se vuelve a consultar RUES


# ── T04: la BD local se sincroniza con lo que resuelve Odoo ───────────────

class CountingCacheRepo(FakeNitCacheRepo):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.save_calls = []

    def save_many(self, results):
        self.save_calls.append([r.name for r in results])
        return super().save_many(results)


def _update(nit, local, odoo, action):
    return {"NIT": nit, "Nombre en BD local": local, "Nombre en Odoo": odoo, "Acción": action}


def test_known_nit_with_different_odoo_name_is_updated():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA NUEVA"}})
    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA VIEJA")})
    uc = _use_case(odoo, cache)

    uc.execute(["111"])

    assert [r.name for r in cache.saved] == ["EMPRESA NUEVA"]
    assert uc.local_updates == [_update("111", "EMPRESA VIEJA", "EMPRESA NUEVA", "Actualizada")]


def test_odoo_nit_missing_locally_is_added():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={})
    uc = _use_case(odoo, cache)

    uc.execute(["111"])

    assert [r.name for r in cache.saved] == ["EMPRESA ODOO"]
    assert uc.local_updates == [_update("111", "", "EMPRESA ODOO", "Agregada")]


def test_odoo_name_used_by_another_nit_is_not_updated_and_marks_conflict():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA NUEVA"}})
    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA VIEJA")}, omit=["111"])
    uc = _use_case(odoo, cache)

    result = uc.execute(["111"])

    assert result[0].conflict
    assert uc.local_updates == [
        _update("111", "EMPRESA VIEJA", "EMPRESA NUEVA", "No actualizada: nombre duplicado en BD local")
    ]


def test_same_name_does_not_write_or_report():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "Empresa  Igual"}})
    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA IGUAL")})
    uc = _use_case(odoo, cache)

    uc.execute(["111"])

    assert cache.saved == [] and uc.local_updates == []


def test_save_is_one_batch_call():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES NUEVA")})
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA NUEVA"}})
    cache = CountingCacheRepo(cached={"111": _cached("111", "EMPRESA VIEJA")})

    _use_case(odoo, cache, scraper).execute(["111", "222"])

    assert cache.save_calls == [["EMPRESA NUEVA", "EMPRESA RUES NUEVA"]]


def test_no_sync_when_odoo_is_unavailable():
    class FailingConnect(FakeOdooRepo):
        def connect(self):
            raise ConnectionError("sin red")

    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA LOCAL")})
    uc = _use_case(FailingConnect(clients={"111": {"id": 1, "name": "NO SE USA"}}), cache)

    result = uc.execute(["111"])

    assert result[0].name == "EMPRESA LOCAL"
    assert cache.saved == [] and uc.local_updates == []


def test_rues_results_are_still_saved_once_and_not_reported_as_odoo_updates():
    scraper = TrackingScraper(results_by_nit={"222": NitResult("222", True, "EMPRESA RUES NUEVA")})
    cache = CountingCacheRepo(cached={})
    uc = _use_case(FakeOdooRepo(), cache, scraper)

    uc.execute(["222"])

    assert cache.save_calls == [["EMPRESA RUES NUEVA"]]
    assert uc.local_updates == []


def test_local_updates_reset_on_each_execute():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA NUEVA"}})
    cache = FakeNitCacheRepo(cached={"111": _cached("111", "EMPRESA VIEJA")})
    uc = _use_case(odoo, cache)
    uc.execute(["111"])

    cache._cached["111"] = _cached("111", "EMPRESA NUEVA")  # la BD local ya quedó al día
    uc.execute(["111"])

    assert uc.local_updates == []
