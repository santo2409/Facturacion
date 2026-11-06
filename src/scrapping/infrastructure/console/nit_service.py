import json
import time

from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    RuesPlaywrightScraper,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_RETRY_DELAY = 5
_MAX_RETRIES = 2


class RUESNitService:
    def __init__(
        self, logger: LoggerAdapter = None, odoo_repo=None, nit_cache_repo=None, scraper=None
    ):
        self.logger = logger or LoggerAdapter(__name__)
        self._scraper = scraper or RuesPlaywrightScraper(logger=self.logger)
        self._use_case = SearchNitsWithOdooFallbackUseCase(
            SearchNitsUseCase(self._scraper),
            odoo_repo=odoo_repo,
            nit_cache_repo=nit_cache_repo,
            logger=self.logger,
        )

    @property
    def local_updates(self) -> list[dict]:
        """Empresas agregadas o corregidas en la BD local con datos de Odoo (última búsqueda)."""
        return self._use_case.local_updates

    @property
    def odoo_available(self) -> bool:
        return self._use_case.odoo_available

    def search(self, nits, rues_cache=None):
        extra = {"rues_cache": rues_cache} if rues_cache is not None else {}
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._use_case.execute(nits, show_progress=False, **extra)
            except Exception as excep:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                else:
                    self.logger.error(f"Error searching NIT {nits}: {excep}", exc_info=True)
                    return None

    def writer(self, data, file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(
                    [d.__dict__ for d in data], file, ensure_ascii=False, indent=2
                )
        except Exception as excep:
            self.logger.error(f"Error writing to file: {excep}", exc_info=True)
