import asyncio
import os

import numpy as np
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from rich.progress import Progress

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.console import console

DEFAULT_CONCURRENCY = 1
MAX_CONCURRENCY = 5


class RuesPlaywrightScraper(NitScraperRepository):
    def __init__(self, logger: LoggerAdapter = None, concurrency: int | None = None):
        self.logger = logger or LoggerAdapter(__name__)
        env_value = os.getenv("RUES_SCRAPER_CONCURRENCY")
        raw = concurrency if concurrency is not None else (int(env_value) if env_value else DEFAULT_CONCURRENCY)
        self.concurrency = max(1, min(raw, MAX_CONCURRENCY))
        self._result_timeout_ms = int(os.getenv("RUES_RESULT_TIMEOUT_MS", "10000"))

    def _prepare_nits(self, nits: list) -> list[int]:
        """Valida y normaliza la lista de NITs de entrada a una lista plana de enteros."""
        if not isinstance(nits, list):
            nits = [nits]
        if nits and not isinstance(nits[0], (list, tuple)):
            nits = [[nit] for nit in nits]

        valid = []
        for nit in nits:
            if nit[0] is None or (isinstance(nit[0], float) and np.isnan(nit[0])):
                continue
            try:
                valid.append(int(str(nit[0]).strip()))
            except (ValueError, TypeError):
                self.logger.error(
                    f"NIT inválido: {nit[0]}",
                    user_msg=f"El NIT {nit[0]} no es válido. Verifique el dato ingresado.",
                )
        return valid

    @staticmethod
    def _split(items: list, n: int) -> list[list]:
        chunks = [items[i::n] for i in range(n)]
        return [c for c in chunks if c]

    async def _search_single_nit(self, page, nit_int: int) -> NitResult:
        my_nit = str(nit_int)[:9]

        input_box = page.locator("input[type='search'], input#search")
        await input_box.wait_for(timeout=5000)
        await input_box.clear()
        await input_box.fill(my_nit)

        submit_button = page.locator(
            "xpath=/html/body/div[1]/div[2]/div/div/div/div[2]/form/button[2]"
        )
        await submit_button.wait_for(timeout=5000)
        await submit_button.click()

        try:
            card_result = page.locator(".card-result").first
            await card_result.wait_for(timeout=self._result_timeout_ms)

            container_html = await page.locator(
                "xpath=/html/body/div[1]/main/div/div/div/div"
            ).inner_html()

            soup = BeautifulSoup(container_html, "html.parser")
            result = soup.find("div", class_="card-result")

            for item in result:
                name_company = item.contents[0].text
                return NitResult(nit=nit_int, is_company=True, name=name_company)
        except PlaywrightTimeoutError:
            pass

        return NitResult(nit=nit_int, is_company=False)

    async def _worker(self, browser, nit_chunk: list[int], progress, task_id) -> list[NitResult]:
        local_results: list[NitResult] = []
        context = await browser.new_context()
        try:
            page = await context.new_page()
            await page.goto("https://www.rues.org.co/", wait_until="networkidle")

            try:
                close_button = page.locator("button.swal2-close")
                await close_button.wait_for(timeout=10000)
                await close_button.click()
            except PlaywrightTimeoutError:
                pass

            for nit_int in nit_chunk:
                try:
                    local_results.append(await self._search_single_nit(page, nit_int))
                except Exception as e:
                    self.logger.error(f"Error buscando NIT {nit_int}: {e}", exc_info=True)
                finally:
                    progress.update(task_id, advance=1)
        except Exception as e:
            self.logger.error(f"Fallo un worker de scraping: {e}", exc_info=True)
        finally:
            await context.close()
        return local_results

    async def _search_nits_async(
        self, nits: list, show_progress: bool = False
    ) -> list[NitResult]:
        """Método asíncrono interno para realizar el scraping"""
        valid_nits = self._prepare_nits(nits)
        if not valid_nits:
            return []
        chunks = self._split(valid_nits, self.concurrency)

        results: list[NitResult] = []
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            try:
                with Progress(console=console, disable=not show_progress) as progress:
                    task_id = progress.add_task("Buscando NITs", total=len(valid_nits))
                    worker_results = await asyncio.gather(
                        *[self._worker(browser, chunk, progress, task_id) for chunk in chunks],
                        return_exceptions=True,
                    )
                for chunk_result in worker_results:
                    if isinstance(chunk_result, Exception):
                        self.logger.error(
                            f"Un worker de scraping falló completamente: {chunk_result}",
                            exc_info=True,
                        )
                        continue
                    results.extend(chunk_result)
            finally:
                await browser.close()
        return results

    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        """Método síncrono que envuelve la lógica asíncrona"""
        return asyncio.run(self._search_nits_async(nits, show_progress))

    def search_by_name(self, name: str) -> NitResult | None:
        """Busca una empresa por nombre en el RUES. Retorna el primer resultado o None."""
        return asyncio.run(self._search_by_name_async(name))

    async def _search_by_name_async(self, name: str) -> NitResult | None:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://www.rues.org.co/", wait_until="networkidle")
                try:
                    close_button = page.locator("button.swal2-close")
                    await close_button.wait_for(timeout=10000)
                    await close_button.click()
                except PlaywrightTimeoutError:
                    pass

                input_box = page.locator("input[type='search'], input#search")
                await input_box.wait_for(timeout=5000)
                await input_box.clear()
                await input_box.fill(name)

                submit_button = page.locator(
                    "xpath=/html/body/div[1]/div[2]/div/div/div/div[2]/form/button[2]"
                )
                await submit_button.wait_for(timeout=5000)
                await submit_button.click()

                try:
                    card_result = page.locator(".card-result").first
                    await card_result.wait_for(timeout=10000)

                    container_html = await page.locator(
                        "xpath=/html/body/div[1]/main/div/div/div/div"
                    ).inner_html()

                    soup = BeautifulSoup(container_html, "html.parser")
                    result = soup.find("div", class_="card-result")

                    for item in result:
                        content = item.contents
                        name_company = content[0].text
                        # Extraer NIT del resultado
                        nit_text = ""
                        for c in content:
                            text = getattr(c, "text", str(c)).strip()
                            if text.isdigit() and 6 <= len(text) <= 12:
                                nit_text = text
                                break
                        if nit_text:
                            return NitResult(nit=int(nit_text), is_company=True, name=name_company)
                except PlaywrightTimeoutError:
                    pass
            except Exception as e:
                self.logger.error(f"Error buscando por nombre '{name}': {e}", exc_info=True)
            finally:
                await browser.close()
        return None
