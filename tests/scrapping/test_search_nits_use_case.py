"""Tests para SearchNitsUseCase."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.domain.entities.nit_result import NitResult


class FakeScraper:
    def __init__(self, results=None):
        self._results = results or []

    def search_nits(self, nits, show_progress=False):
        return self._results


def test_execute_returns_results():
    results = [NitResult(900111111, True, "EMPRESA A")]
    scraper = FakeScraper(results)
    uc = SearchNitsUseCase(scraper)
    assert uc.execute(["900111111"]) == results


def test_execute_empty_nits():
    scraper = FakeScraper([])
    uc = SearchNitsUseCase(scraper)
    assert uc.execute([]) == []


def test_execute_passes_show_progress():
    class TrackingScraper:
        def __init__(self):
            self.called_with_progress = None

        def search_nits(self, nits, show_progress=False):
            self.called_with_progress = show_progress
            return []

    scraper = TrackingScraper()
    uc = SearchNitsUseCase(scraper)
    uc.execute(["123"], show_progress=True)
    assert scraper.called_with_progress is True
