from src.company.domain.entities.company import Company
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    RuesPlaywrightScraper,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class RUESNitService:
    def __init__(self, logger: LoggerAdapter = None):
        self.logger = logger or LoggerAdapter(__name__)

    def search(self, nit):
        try:
            scraper = RuesPlaywrightScraper()
            use_case = SearchNitsUseCase(scraper)
            data = use_case.execute(nit)
            if not data:
                return None
            name, nit = data[0].company, data[0].nit
            return Company(nit=nit, name=name)
        except Exception as excep:
            self.logger.error(f"Error searching NIT {nit}: {excep}", exc_info=True)
