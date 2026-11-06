from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)


class SearchNitsUseCase:
    def __init__(self, scraper: NitScraperRepository):
        self.scraper = scraper

    def execute(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        return self.scraper.search_nits(nits, show_progress)

    def execute_names(
        self, names: list[str], show_progress: bool = False
    ) -> dict[str, NitResult]:
        return self.scraper.search_names(names, show_progress)
