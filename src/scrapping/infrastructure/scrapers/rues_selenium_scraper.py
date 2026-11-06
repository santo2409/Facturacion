import asyncio
import math
import os

from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from rich.progress import Progress

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_scraper_repository import (
    NitScraperRepository,
)
from src.shared.config import get_int_env
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.console import console

DEFAULT_CONCURRENCY = 1
MAX_CONCURRENCY = 5
DEFAULT_REQUEST_DELAY_MS = 1000

RUES_URL = "https://www.rues.org.co/"
_SEARCH_INPUT = "input[type='search'], input#search"
_SUBMIT_BUTTON = "xpath=/html/body/div[1]/div[2]/div/div/div/div[2]/form/button[2]"
_RESULTS_CONTAINER = "xpath=/html/body/div[1]/main/div/div/div/div"
_MODAL_CLOSE = "button.swal2-close"


class RuesPlaywrightScraper(NitScraperRepository):
    def __init__(
        self,
        logger: LoggerAdapter = None,
        concurrency: int | None = None,
        browser_factory=None,
    ):
        self.logger = logger or LoggerAdapter(__name__)
        env_value = os.getenv("RUES_SCRAPER_CONCURRENCY")
        raw = concurrency if concurrency is not None else (int(env_value) if env_value else DEFAULT_CONCURRENCY)
        self.concurrency = max(1, min(raw, MAX_CONCURRENCY))
        self._result_timeout_ms = get_int_env("RUES_RESULT_TIMEOUT_MS", 10000)
        self._request_delay_ms = get_int_env("RUES_REQUEST_DELAY_MS", DEFAULT_REQUEST_DELAY_MS)
        self._browser_factory = browser_factory or async_playwright

    def _prepare_nits(self, nits: list) -> list[int]:
        """Valida y normaliza la lista de NITs de entrada a una lista plana de enteros."""
        if not isinstance(nits, list):
            nits = [nits]
        if nits and not isinstance(nits[0], (list, tuple)):
            nits = [[nit] for nit in nits]

        valid = []
        for nit in nits:
            if nit[0] is None or (isinstance(nit[0], float) and math.isnan(nit[0])):
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

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def _open_page(self, context):
        """Abre la página de RUES y descarta el modal de bienvenida."""
        page = await context.new_page()
        await page.goto(RUES_URL, wait_until="networkidle")
        try:
            close_button = page.locator(_MODAL_CLOSE)
            await close_button.wait_for(timeout=10000)
            await close_button.click()
        except PlaywrightTimeoutError:
            pass
        return page

    async def _submit_search(self, page, term: str) -> None:
        input_box = page.locator(_SEARCH_INPUT)
        await input_box.wait_for(timeout=5000)
        await input_box.clear()
        await input_box.fill(term)

        submit_button = page.locator(_SUBMIT_BUTTON)
        await submit_button.wait_for(timeout=5000)
        await submit_button.click()

    async def _first_card(self, page):
        """Devuelve el primer `.card-result` de la página, o None si no aparece."""
        try:
            card_result = page.locator(".card-result").first
            await card_result.wait_for(timeout=self._result_timeout_ms)
            container_html = await page.locator(_RESULTS_CONTAINER).inner_html()
        except PlaywrightTimeoutError:
            return None

        soup = BeautifulSoup(container_html, "html.parser")
        return soup.find("div", class_="card-result")

    async def _search_single_nit(self, page, nit_int: int) -> NitResult:
        await self._submit_search(page, str(nit_int)[:9])

        card = await self._first_card(page)
        if card:
            for item in card:
                return NitResult(nit=nit_int, is_company=True, name=item.contents[0].text)

        return NitResult(nit=nit_int, is_company=False)

    async def _search_single_name(self, page, name: str) -> NitResult | None:
        await self._submit_search(page, name)

        card = await self._first_card(page)
        if not card:
            return None

        for item in card:
            content = item.contents
            name_company = content[0].text
            nit_text = ""
            for c in content:
                text = getattr(c, "text", str(c)).strip()
                if text.isdigit() and 6 <= len(text) <= 12:
                    nit_text = text
                    break
            if nit_text:
                return NitResult(nit=int(nit_text), is_company=True, name=name_company)

        return None

    async def _worker(self, browser, chunk: list, progress, task_id, search_fn) -> list[tuple]:
        """Procesa un chunk en una sola página, emparejando cada ítem con su resultado."""
        pairs: list[tuple] = []
        context = await browser.new_context()
        try:
            page = await self._open_page(context)

            for index, item in enumerate(chunk):
                try:
                    pairs.append((item, await search_fn(page, item)))
                except Exception as e:
                    self.logger.error(f"Error consultando '{item}' en RUES: {e}", exc_info=True)
                finally:
                    progress.update(task_id, advance=1)

                if self._request_delay_ms and index < len(chunk) - 1:
                    await self._sleep(self._request_delay_ms / 1000)
        except Exception as e:
            self.logger.error(f"Falló un worker de scraping: {e}", exc_info=True)
        finally:
            await context.close()
        return pairs

    async def _run_batch(
        self, items: list, search_fn, description: str, show_progress: bool
    ) -> list[tuple]:
        """Lanza UN navegador y reparte los ítems entre workers concurrentes."""
        if not items:
            return []

        chunks = self._split(items, self.concurrency)
        pairs: list[tuple] = []

        async with self._browser_factory() as p:
            browser = await p.firefox.launch(headless=True)
            try:
                with Progress(console=console, disable=not show_progress) as progress:
                    task_id = progress.add_task(description, total=len(items))
                    worker_results = await asyncio.gather(
                        *[
                            self._worker(browser, chunk, progress, task_id, search_fn)
                            for chunk in chunks
                        ],
                        return_exceptions=True,
                    )
                for chunk_result in worker_results:
                    if isinstance(chunk_result, Exception):
                        self.logger.error(
                            f"Un worker de scraping falló completamente: {chunk_result}",
                            exc_info=True,
                        )
                        continue
                    pairs.extend(chunk_result)
            finally:
                await browser.close()
        return pairs

    async def _search_nits_async(
        self, nits: list, show_progress: bool = False
    ) -> list[NitResult]:
        valid_nits = self._prepare_nits(nits)
        pairs = await self._run_batch(
            valid_nits, self._search_single_nit, "Buscando NITs", show_progress
        )
        return [result for _, result in pairs if result is not None]

    async def _search_names_async(
        self, names: list[str], show_progress: bool = False
    ) -> dict[str, NitResult]:
        cleaned = [name for name in dict.fromkeys(names) if name and name.strip()]
        pairs = await self._run_batch(
            cleaned, self._search_single_name, "Buscando empresas por nombre", show_progress
        )
        return {name: result for name, result in pairs if result is not None}

    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        """Método síncrono que envuelve la lógica asíncrona"""
        return asyncio.run(self._search_nits_async(nits, show_progress))

    def search_names(
        self, names: list[str], show_progress: bool = False
    ) -> dict[str, NitResult]:
        """Busca varias empresas por nombre reutilizando un único navegador."""
        return asyncio.run(self._search_names_async(names, show_progress))

    def search_by_name(self, name: str) -> NitResult | None:
        """Busca una empresa por nombre en el RUES. Retorna el primer resultado o None."""
        return self.search_names([name]).get(name)
