"""Tests de la cascada de 7 pasos de SearchNitsWithOdooFallbackUseCase."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.utils.company_name_matcher import CompanyNameMatcher
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_nit_scraper import FakeNitScraper
from tests.fakes.fake_odoo_repo import FakeOdooRepo


def matcher():
    return CompanyNameMatcher(FakeFuzz())


def build(scraper=None, odoo=None, cache=None, logger=None, **kwargs):
    scraper = scraper or FakeNitScraper()
    return SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper),
        odoo_repo=odoo,
        nit_cache_repo=cache,
        logger=logger or FakeLogger(),
        name_matcher=kwargs.pop("name_matcher", matcher()),
        **kwargs,
    )


# ── T13: detección de novedades ──────────────────────────────────────────────


def test_no_novelty_when_resolved_by_nit():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA UNO"}})
    uc = build(odoo=odoo)

    result = uc.execute(["111"], book_names={"111": "EMPRESA UNO"})

    assert result[0].nit_original is None
    assert result[0].name_original is None


def test_name_correction_is_flagged_when_names_differ():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA UNO SAS"}})
    uc = build(odoo=odoo)

    result = uc.execute(["111"], book_names={"111": "EMPRESA VIEJA"})

    assert result[0].name_original == "EMPRESA VIEJA"
    assert result[0].name == "EMPRESA UNO SAS"


def test_format_only_differences_are_not_flagged_as_novelty():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "CLINICA X SAS"}})
    uc = build(odoo=odoo)

    result = uc.execute(["111"], book_names={"111": "Clínica X S.A.S."})

    assert result[0].name_original is None


# ── T01: _names_differ con fallback difuso ───────────────────────────────────


class RecordingFuzz:
    def __init__(self, result=None):
        self._result = result
        self.calls = []

    def fuzz_property(self, name, catalog, threshold=90):
        self.calls.append({"name": name, "catalog": catalog, "threshold": threshold})
        return self._result


def test_names_differ_returns_false_when_book_name_is_empty():
    uc = build()

    assert uc._names_differ(None, "EMPRESA A") is False
    assert uc._names_differ("", "EMPRESA A") is False


def test_names_differ_uses_matcher_when_available():
    from src.shared.utils.company_name_matcher import CompanyNameMatcher

    uc = build(name_matcher=CompanyNameMatcher(FakeFuzz()))

    assert uc._names_differ("EMPRESA A", "EMPRESA A") is False
    assert uc._names_differ("EMPRESA A", "OTRA COSA") is True


def test_names_differ_treats_no_match_from_matcher_as_different():
    from src.shared.utils.company_name_matcher import CompanyNameMatcher

    uc = build(name_matcher=CompanyNameMatcher(RecordingFuzz(result=None)))

    assert uc._names_differ("EMPRESA A", "EMPRESA A") is True


def test_names_differ_falls_back_to_exact_comparison_without_matcher():
    uc = build(name_matcher=None)

    assert uc._names_differ("Empresa A", "EMPRESA A") is False
    assert uc._names_differ("VR INGENIERIA SAS", "V R INGENIERIA SAS") is True


# ── T02: integración con RapidFuzz real, casos de producción ────────────────


def test_name_correction_is_not_flagged_for_suffix_formatting_variance():
    """Caso real de data.json: mismo NIT ya en BD local con un nombre que
    solo difiere en el espaciado del sufijo societario."""
    from src.shared.utils.company_name_matcher import CompanyNameMatcher
    from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller

    real_matcher = CompanyNameMatcher(RapidFuzzBiller(FakeLogger()))
    cache = FakeNitCacheRepo(
        cached={
            "111": NitResult(
                "111", True, "V R INGENIERIA Y MERCADEO SAS", "BD local"
            )
        }
    )
    uc = build(cache=cache, name_matcher=real_matcher)

    result = uc.execute(
        ["111"], book_names={"111": "VR INGENIERIA  Y MERCADEO SAS"}
    )

    assert result[0].name_original is None


def test_name_correction_is_still_flagged_for_genuinely_different_names():
    """Caso real de data.json: mismo NIT, pero el nombre en BD local
    corresponde a una empresa distinta — debe seguir marcándose."""
    from src.shared.utils.company_name_matcher import CompanyNameMatcher
    from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller

    real_matcher = CompanyNameMatcher(RapidFuzzBiller(FakeLogger()))
    cache = FakeNitCacheRepo(
        cached={
            "39631107": NitResult(
                "39631107", True, "ELVIA ROSA CAMACHO SAAVEDRA", "BD local"
            )
        }
    )
    uc = build(cache=cache, name_matcher=real_matcher)

    result = uc.execute(
        ["39631107"], book_names={"39631107": "DROGUERIAS RONID SAS"}
    )

    assert result[0].name_original == "DROGUERIAS RONID SAS"


# ── T14: pasos 1-2, BD local ─────────────────────────────────────────────────


def test_local_db_by_nit_short_circuits_rues_when_odoo_has_no_data():
    # spec 016: Odoo se consulta primero; la BD local es el respaldo y evita RUES
    scraper = FakeNitScraper()
    odoo = FakeOdooRepo(clients={})
    cache = FakeNitCacheRepo(
        cached={"111": NitResult("111", True, "EMPRESA CACHEADA", "BD local")}
    )
    uc = build(scraper=scraper, odoo=odoo, cache=cache)

    result = uc.execute(["111"])

    assert result[0].name == "EMPRESA CACHEADA"
    assert result[0].checked_bases == "BD local"
    assert scraper.search_nits_calls == []


def test_local_db_by_name_resolves_when_nit_missing():
    cache = FakeNitCacheRepo(
        cached_by_name={
            "EMPRESA UNO": NitResult("111", True, "EMPRESA UNO", "BD local")
        }
    )
    uc = build(cache=cache)

    result = uc.execute(["999"], book_names={"999": "EMPRESA UNO"})

    assert result[0].is_company is True
    assert result[0].nit == "111"
    assert result[0].nit_original == "999"


def test_local_name_lookup_can_be_disabled():
    cache = FakeNitCacheRepo(
        cached_by_name={
            "EMPRESA UNO": NitResult("111", True, "EMPRESA UNO", "BD local")
        }
    )
    uc = build(cache=cache, local_name_lookup=False)

    result = uc.execute(["999"], book_names={"999": "EMPRESA UNO"})

    assert result[0].is_company is False


# ── T15: paso 3, Odoo por NIT ────────────────────────────────────────────────


def test_odoo_by_nit_runs_after_local_db():
    cache = FakeNitCacheRepo(cached={})
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    uc = build(odoo=odoo, cache=cache)

    result = uc.execute(["111"])

    assert result[0].name == "EMPRESA ODOO"
    assert result[0].checked_bases == "Odoo"
    assert result[0].source == "Odoo/NIT"


# ── T16: paso 4, Odoo por nombre ─────────────────────────────────────────────


def test_odoo_by_name_resolves_and_propagates_found_nit():
    odoo = FakeOdooRepo(clients={"900111222": {"id": 1, "name": "EMPRESA A SAS"}})
    uc = build(odoo=odoo)

    result = uc.execute(["900111111"], book_names={"900111111": "EMPRESA A SAS"})

    assert result[0].is_company is True
    assert result[0].nit == "900111222"
    assert result[0].nit_original == "900111111"
    assert result[0].source == "Odoo/nombre"


def test_odoo_by_name_below_threshold_falls_through_to_rues():
    odoo = FakeOdooRepo(clients={"900111222": {"id": 1, "name": "OTRA COSA MUY DISTINTA"}})
    scraper = FakeNitScraper()
    uc = build(scraper=scraper, odoo=odoo)

    result = uc.execute(["900111111"], book_names={"900111111": "EMPRESA A SAS"})

    assert result[0].is_company is False
    assert scraper.search_nits_calls == [["900111111"]]


def test_odoo_by_name_without_vat_is_not_resolved():
    class NoVatOdooRepo(FakeOdooRepo):
        def find_clients_by_name(self, name, limit=10):
            return [{"id": 1, "name": "EMPRESA A SAS", "vat": ""}]

    uc = build(odoo=NoVatOdooRepo(clients={}))

    result = uc.execute(["900111111"], book_names={"900111111": "EMPRESA A SAS"})

    assert result[0].is_company is False


def test_odoo_by_name_queries_each_distinct_name_once():
    class CountingOdooRepo(FakeOdooRepo):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.name_queries = []

        def find_clients_by_name(self, name, limit=10):
            self.name_queries.append(name)
            return super().find_clients_by_name(name, limit)

    odoo = CountingOdooRepo(clients={})
    uc = build(odoo=odoo)

    uc.execute(
        ["111", "222"], book_names={"111": "EMPRESA A", "222": "EMPRESA A"}
    )

    assert odoo.name_queries == ["EMPRESA A"]


def test_name_steps_are_skipped_without_matcher():
    class CountingOdooRepo(FakeOdooRepo):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.name_queries = []

        def find_clients_by_name(self, name, limit=10):
            self.name_queries.append(name)
            return super().find_clients_by_name(name, limit)

    odoo = CountingOdooRepo(clients={})
    uc = build(odoo=odoo, name_matcher=None)

    uc.execute(["111"], book_names={"111": "EMPRESA A"})

    assert odoo.name_queries == []


# ── T17: paso 5, RUES por NIT ────────────────────────────────────────────────


def test_rues_results_matched_by_normalized_nit():
    scraper = FakeNitScraper(
        by_nit={"900.123.456-9": NitResult(900123456, True, "EMPRESA RUES")}
    )
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}))

    result = uc.execute(["900.123.456-9"])

    assert result[0].name == "EMPRESA RUES"
    assert result[0].checked_bases == "Odoo, RUES"
    assert result[0].source == "RUES/NIT"


def test_rues_returning_fewer_results_leaves_rest_not_found():
    scraper = FakeNitScraper(
        by_nit={"111": NitResult("111", True, "EMPRESA RUES")}, omit=["222"]
    )
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}))

    result = uc.execute(["111", "222"])

    assert result[0].is_company is True
    assert result[1].is_company is False


# ── T18: paso 6, RUES por nombre ─────────────────────────────────────────────


def test_rues_by_name_resolves_and_propagates_found_nit():
    scraper = FakeNitScraper(
        by_name={"EMPRESA A SAS": NitResult(900111222, True, "EMPRESA A SAS")}
    )
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}))

    result = uc.execute(["900111111"], book_names={"900111111": "EMPRESA A SAS"})

    assert result[0].is_company is True
    assert result[0].nit == "900111222"
    assert result[0].nit_original == "900111111"
    assert result[0].source == "RUES/nombre"


def test_rues_by_name_below_threshold_is_discarded():
    scraper = FakeNitScraper(
        by_name={"EMPRESA A SAS": NitResult(900111222, True, "OTRA COSA DISTINTA")}
    )
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}))

    result = uc.execute(["900111111"], book_names={"900111111": "EMPRESA A SAS"})

    assert result[0].is_company is False


def test_rues_by_name_deduplicates_names_before_query():
    scraper = FakeNitScraper()
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}))

    uc.execute(["111", "222"], book_names={"111": "EMPRESA A", "222": "EMPRESA A"})

    assert scraper.search_names_calls == [["EMPRESA A"]]


def test_rues_by_name_respects_lookup_limit_and_warns_user():
    scraper = FakeNitScraper()
    logger = FakeLogger()
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}), logger=logger, rues_name_limit=1)

    uc.execute(["111", "222"], book_names={"111": "EMPRESA A", "222": "EMPRESA B"})

    assert scraper.search_names_calls == [["EMPRESA A"]]
    assert logger.warnings


# ── T19: ensamblado e invariante ─────────────────────────────────────────────


def test_returns_one_result_per_input_nit_in_order():
    scraper = FakeNitScraper(by_nit={"222": NitResult("222", True, "EMPRESA RUES")})
    odoo = FakeOdooRepo(clients={"333": {"id": 3, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(
        cached={"111": NitResult("111", True, "EMPRESA CACHEADA", "BD local")}
    )
    uc = build(scraper=scraper, odoo=odoo, cache=cache)

    result = uc.execute(["111", "222", "333", "999"])

    assert [r.nit for r in result] == ["111", "222", "333", "999"]
    assert [r.name for r in result] == [
        "EMPRESA CACHEADA",
        "EMPRESA RUES",
        "EMPRESA ODOO",
        None,
    ]


# ── T20: persistencia y conflicto ────────────────────────────────────────────


def test_company_found_in_odoo_and_missing_locally_is_saved():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={})
    uc = build(odoo=odoo, cache=cache)

    uc.execute(["111"])

    assert [r.name for r in cache.saved] == ["EMPRESA ODOO"]


def test_already_cached_company_is_not_saved_again():
    cache = FakeNitCacheRepo(
        cached={"111": NitResult("111", True, "EMPRESA CACHEADA", "BD local")}
    )
    uc = build(cache=cache)

    uc.execute(["111"])

    assert cache.saved == []


def test_omitted_company_is_flagged_as_conflict():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={}, omit=["111"])
    uc = build(odoo=odoo, cache=cache)

    result = uc.execute(["111"])

    assert result[0].conflict


# ── T21: degradación ─────────────────────────────────────────────────────────


def test_odoo_connection_failure_degrades_with_warning():
    class FailingOdooRepo(FakeOdooRepo):
        def connect(self):
            raise ConnectionError("Autenticación fallida")

    scraper = FakeNitScraper(by_nit={"111": NitResult("111", True, "EMPRESA RUES")})
    logger = FakeLogger()
    uc = build(scraper=scraper, odoo=FailingOdooRepo(), logger=logger)

    result = uc.execute(["111"])

    assert result[0].name == "EMPRESA RUES"
    assert result[0].checked_bases == "RUES"
    assert logger.warnings


def test_name_step_exception_logs_warning_and_continues():
    class FailingNameOdooRepo(FakeOdooRepo):
        def find_clients_by_name(self, name, limit=10):
            raise ConnectionError("Timeout")

    scraper = FakeNitScraper(by_nit={"111": NitResult("111", True, "EMPRESA RUES")})
    logger = FakeLogger()
    uc = build(scraper=scraper, odoo=FailingNameOdooRepo(clients={}), logger=logger)

    result = uc.execute(["111"], book_names={"111": "EMPRESA A"})

    assert result[0].name == "EMPRESA RUES"
    assert logger.warnings


def test_local_name_lookup_failure_does_not_break_cascade():
    class FailingCache(FakeNitCacheRepo):
        def get_by_names(self, names):
            raise ConnectionError("BD no disponible")

    # Odoo no tiene el NIT: la búsqueda local por nombre falla y la cascada sigue a RUES
    scraper = FakeNitScraper(by_nit={"111": NitResult("111", True, "EMPRESA RUES")})
    logger = FakeLogger()
    uc = build(scraper=scraper, odoo=FakeOdooRepo(clients={}), cache=FailingCache(cached={}), logger=logger)

    result = uc.execute(["111"], book_names={"111": "EMPRESA A"})

    assert result[0].name == "EMPRESA RUES"
    assert logger.warnings
