from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)


class MinimalScraper(NitScraperRepository):
    """Adaptador que solo implementa lo abstracto: hereda search_names por defecto."""

    def __init__(self, by_name=None):
        self._by_name = by_name or {}
        self.name_calls = []

    def search_nits(self, nits, show_progress=False):
        return []

    def search_by_name(self, name):
        self.name_calls.append(name)
        return self._by_name.get(name)


def test_search_names_default_delegates_to_search_by_name():
    scraper = MinimalScraper(
        {"EMPRESA A": NitResult(nit=900111111, is_company=True, name="EMPRESA A")}
    )

    result = scraper.search_names(["EMPRESA A"])

    assert result["EMPRESA A"].nit == 900111111
    assert scraper.name_calls == ["EMPRESA A"]


def test_search_names_default_omits_none_results():
    scraper = MinimalScraper(
        {"EMPRESA A": NitResult(nit=900111111, is_company=True, name="EMPRESA A")}
    )

    result = scraper.search_names(["EMPRESA A", "NO EXISTE"])

    assert list(result) == ["EMPRESA A"]


def test_search_names_default_with_empty_list():
    assert MinimalScraper().search_names([]) == {}
