import numpy as np
import requests
from rich.progress import track

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class DatosGovScraper(NitScraperRepository):
    def __init__(self, logger: LoggerAdapter = None):
        self.api_url = "https://www.datos.gov.co/resource/c82u-588k.json"
        self.logger = logger or LoggerAdapter(__name__)

    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        # Normalizar entrada: si es un solo NIT, convertir a lista
        if not isinstance(nits, list):
            nits = [nits]
        if nits and not isinstance(nits[0], (list, tuple)):
            nits = [[nit] for nit in nits]

        list_nits = []
        iterator = track(nits, description="Buscando NITs") if show_progress else nits

        for nit in iterator:
            if nit[0] is None or (isinstance(nit[0], float) and np.isnan(nit[0])):
                continue

            try:
                nit_int = int(str(nit[0]).strip())
            except (ValueError, TypeError):
                continue

            my_nit = str(nit_int)[:9]

            url = f"{self.api_url}?nit={my_nit}"

            try:
                response = requests.get(url)
                response.raise_for_status()

                data = response.json()

                if not data:
                    list_nits.append(
                        NitResult(nit=nit_int, is_company=False, name=None)
                    )
                else:
                    empresa = data[0]
                    razon_social = empresa.get("razon_social", "Sin nombre")
                    list_nits.append(
                        NitResult(nit=nit_int, is_company=True, name=razon_social)
                    )

            except requests.exceptions.RequestException as e:
                self.logger.error(
                    f"Error fetching data for NIT {nit_int}: {e}", exc_info=True,
                    user_msg=f"No se pudo obtener información del NIT {nit_int}."
                )
                list_nits.append(NitResult(nit=nit_int, is_company=False, name=None))

        return list_nits
