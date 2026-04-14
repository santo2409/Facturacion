import json

from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    RuesPlaywrightScraper,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class RUESNitService:
    def __init__(self, logger: LoggerAdapter = None):
        self.logger = logger or LoggerAdapter(__name__)

    def search(self, nits):
        try:
            scraper = RuesPlaywrightScraper()
            use_case = SearchNitsUseCase(scraper)
            data = use_case.execute(nits, show_progress=True)

            return data
        except Exception as excep:
            self.logger.error(f"Error searching NIT {nits}: {excep}", exc_info=True, user_msg="No se pudo consultar el NIT. Verifique su conexión e intente nuevamente.")
            return None

    def writer(self, data, file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(
                    [d.__dict__ for d in data], file, ensure_ascii=False, indent=2
                )
        except Exception as excep:
            self.logger.error(f"Error writing to file: {excep}", exc_info=True, user_msg="No se pudo guardar el archivo de resultados.")
