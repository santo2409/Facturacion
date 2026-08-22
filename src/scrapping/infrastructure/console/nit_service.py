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
    def __init__(self, logger: LoggerAdapter = None, odoo_repo=None, nit_cache_repo=None):
        self.logger = logger or LoggerAdapter(__name__)
        self._scraper = RuesPlaywrightScraper(logger=self.logger)
        self._use_case = SearchNitsWithOdooFallbackUseCase(
            SearchNitsUseCase(self._scraper),
            odoo_repo=odoo_repo,
            nit_cache_repo=nit_cache_repo,
            logger=self.logger,
        )

    def search(self, nits):
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._use_case.execute(nits, show_progress=False)
            except Exception as excep:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                else:
                    self.logger.error(f"Error searching NIT {nits}: {excep}", exc_info=True)
                    return None

    def search_by_name(self, name: str):
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._scraper.search_by_name(name)
            except Exception as excep:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                else:
                    self.logger.error(f"Error buscando por nombre '{name}': {excep}", exc_info=True)
                    return None

    def writer(self, data, file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(
                    [d.__dict__ for d in data], file, ensure_ascii=False, indent=2
                )
        except Exception as excep:
            self.logger.error(f"Error writing to file: {excep}", exc_info=True)
