import asyncio

import numpy as np
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from rich.progress import track

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.console import console


class RuesPlaywrightScraper(NitScraperRepository):
    def __init__(self, logger: LoggerAdapter = None):
        self.logger = logger or LoggerAdapter(__name__)

    async def _search_nits_async(
        self, nits: list, show_progress: bool = False
    ) -> list[NitResult]:
        """Método asíncrono interno para realizar el scraping"""
        if not isinstance(nits, list):
            nits = [nits]
        if nits and not isinstance(nits[0], (list, tuple)):
            nits = [[nit] for nit in nits]

        list_nits = []

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto("https://www.rues.org.co/", wait_until="networkidle")

                # Cerrar modal si existe
                try:
                    close_button = page.locator("button.swal2-close")
                    await close_button.wait_for(timeout=10000)
                    await close_button.click()
                except PlaywrightTimeoutError:
                    None

                iterator = (
                    track(nits, description="Buscando NITs", console=console)
                    if show_progress
                    else nits
                )
                for nit in iterator:
                    if nit[0] is None or (
                        isinstance(nit[0], float) and np.isnan(nit[0])
                    ):
                        continue

                    try:
                        nit_int = int(str(nit[0]).strip())
                    except (ValueError, TypeError):
                        self.logger.error(f"NIT inválido: {nit[0]}")
                        continue

                    my_nit = str(nit_int)[:9]

                    # Ingresar NIT en el campo de búsqueda
                    input_box = page.locator("input[type='search'], input#search")
                    await input_box.wait_for(timeout=5000)
                    await input_box.clear()
                    await input_box.fill(my_nit)

                    # Hacer clic en el botón de búsqueda
                    submit_button = page.locator(
                        "xpath=/html/body/div[1]/div[2]/div/div/div/div[2]/form/button[2]"
                    )
                    await submit_button.wait_for(timeout=5000)
                    await submit_button.click()

                    # Esperar resultados
                    try:
                        card_result = page.locator(".card-result").first
                        await card_result.wait_for(timeout=10000)

                        # Obtener el HTML del contenedor
                        container_html = await page.locator(
                            "xpath=/html/body/div[1]/main/div/div/div/div"
                        ).inner_html()

                        soup = BeautifulSoup(container_html, "html.parser")
                        result = soup.find("div", class_="card-result")

                        for item in result:
                            content = item.contents
                            name_company = content[0].text

                            list_nits.append(
                                NitResult(
                                    nit=nit_int,
                                    is_company=True,
                                    company=name_company,
                                )
                            )
                            break

                    except PlaywrightTimeoutError:
                        list_nits.append(NitResult(nit=nit_int, is_company=False))

            except Exception as e:
                self.logger.error(f"Error durante el scraping: {e}", exc_info=True)
            finally:
                await browser.close()

        return list_nits

    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        """Método síncrono que envuelve la lógica asíncrona"""
        return asyncio.run(self._search_nits_async(nits, show_progress))
