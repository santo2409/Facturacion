"""Tests del motor de scraping en lote de RuesPlaywrightScraper (sin red ni browser)."""
import asyncio

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    RuesPlaywrightScraper,
)
from tests.fakes.fake_logger import FakeLogger

CARD_HTML = (
    '<div class="card-result"><div>'
    "<span>EMPRESA A SAS</span><span>900111111</span>"
    "</div></div>"
)
CARD_HTML_WITHOUT_NIT = (
    '<div class="card-result"><div><span>EMPRESA A SAS</span></div></div>'
)


class FakeLocator:
    def __init__(self, html="", timeout=False):
        self.html = html
        self.timeout = timeout
        self.filled = []
        self.clicks = 0

    @property
    def first(self):
        return self

    async def wait_for(self, timeout=None):
        if self.timeout:
            raise PlaywrightTimeoutError("timeout")

    async def clear(self):
        pass

    async def fill(self, value):
        self.filled.append(value)

    async def click(self):
        self.clicks += 1

    async def inner_html(self):
        return self.html


class FakePage:
    def __init__(self, card_html="", card_timeout=False, modal_timeout=False):
        self._card_html = card_html
        self._card_timeout = card_timeout
        self._modal_timeout = modal_timeout
        self.goto_calls = []
        self.locators = {}

    async def goto(self, url, wait_until=None):
        self.goto_calls.append(url)

    def locator(self, selector):
        if selector not in self.locators:
            if selector == ".card-result":
                loc = FakeLocator(timeout=self._card_timeout)
            elif selector == "button.swal2-close":
                loc = FakeLocator(timeout=self._modal_timeout)
            elif selector.startswith("xpath=/html/body/div[1]/main"):
                loc = FakeLocator(html=self._card_html)
            else:
                loc = FakeLocator()
            self.locators[selector] = loc
        return self.locators[selector]


class FakeContext:
    def __init__(self, page_factory):
        self._page_factory = page_factory
        self.pages = []
        self.closed = False

    async def new_page(self):
        page = self._page_factory()
        self.pages.append(page)
        return page

    async def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, page_factory):
        self._page_factory = page_factory
        self.contexts = []
        self.closed = False

    async def new_context(self):
        context = FakeContext(self._page_factory)
        self.contexts.append(context)
        return context

    async def close(self):
        self.closed = True


class FakeBrowserFactory:
    """Sustituye async_playwright(): permite contar los navegadores lanzados."""

    def __init__(self, page_factory=None):
        self._page_factory = page_factory or FakePage
        self.browsers = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    @property
    def firefox(self):
        return self

    async def launch(self, headless=True):
        browser = FakeBrowser(self._page_factory)
        self.browsers.append(browser)
        return browser


def build_scraper(factory, concurrency=1, delay_ms=0):
    scraper = RuesPlaywrightScraper(
        logger=FakeLogger(), concurrency=concurrency, browser_factory=factory
    )
    scraper._request_delay_ms = delay_ms
    return scraper


async def echo_search(page, item):
    return f"resultado-{item}"


# ── Helpers compartidos (T07) ────────────────────────────────────────────────


def test_open_page_navigates_and_closes_modal():
    scraper = build_scraper(FakeBrowserFactory())
    context = FakeContext(FakePage)

    page = asyncio.run(scraper._open_page(context))

    assert page.goto_calls == ["https://www.rues.org.co/"]
    assert page.locators["button.swal2-close"].clicks == 1


def test_open_page_tolerates_missing_modal():
    scraper = build_scraper(FakeBrowserFactory())
    context = FakeContext(lambda: FakePage(modal_timeout=True))

    page = asyncio.run(scraper._open_page(context))

    assert page.goto_calls == ["https://www.rues.org.co/"]


def test_submit_search_fills_input_and_clicks_button():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage()

    asyncio.run(scraper._submit_search(page, "900111111"))

    assert page.locators["input[type='search'], input#search"].filled == ["900111111"]
    assert page.locators[
        "xpath=/html/body/div[1]/div[2]/div/div/div/div[2]/form/button[2]"
    ].clicks == 1


def test_first_card_returns_none_on_timeout():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_timeout=True)

    assert asyncio.run(scraper._first_card(page)) is None


def test_search_single_nit_returns_company_from_card():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_html=CARD_HTML)

    result = asyncio.run(scraper._search_single_nit(page, 900111111))

    assert result.is_company is True
    assert result.name == "EMPRESA A SAS"


def test_search_single_nit_returns_not_found_on_timeout():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_timeout=True)

    result = asyncio.run(scraper._search_single_nit(page, 900111111))

    assert result.is_company is False
    assert result.nit == 900111111


def test_search_single_nit_truncates_to_nine_digits():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_html=CARD_HTML)

    asyncio.run(scraper._search_single_nit(page, 9001111119))

    assert page.locators["input[type='search'], input#search"].filled == ["900111111"]


def test_search_single_name_extracts_nit_from_card():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_html=CARD_HTML)

    result = asyncio.run(scraper._search_single_name(page, "EMPRESA A SAS"))

    assert result.nit == 900111111
    assert result.name == "EMPRESA A SAS"


def test_search_single_name_returns_none_when_no_digits_found():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_html=CARD_HTML_WITHOUT_NIT)

    assert asyncio.run(scraper._search_single_name(page, "EMPRESA A SAS")) is None


def test_search_single_name_returns_none_on_timeout():
    scraper = build_scraper(FakeBrowserFactory())
    page = FakePage(card_timeout=True)

    assert asyncio.run(scraper._search_single_name(page, "EMPRESA A SAS")) is None


# ── Motor batch (T08) ────────────────────────────────────────────────────────


def test_run_batch_launches_single_browser_for_many_items():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory)

    asyncio.run(scraper._run_batch(["a", "b", "c", "d"], echo_search, "test", False))

    assert len(factory.browsers) == 1


def test_run_batch_splits_items_according_to_concurrency():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory, concurrency=2)

    asyncio.run(scraper._run_batch(["a", "b", "c", "d"], echo_search, "test", False))

    assert len(factory.browsers[0].contexts) == 2


def test_run_batch_closes_browser_and_contexts():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory)

    asyncio.run(scraper._run_batch(["a"], echo_search, "test", False))

    assert factory.browsers[0].closed is True
    assert factory.browsers[0].contexts[0].closed is True


def test_run_batch_pairs_results_by_key_not_by_position():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory)

    async def only_b(page, item):
        return f"ok-{item}" if item == "b" else None

    pairs = asyncio.run(scraper._run_batch(["a", "b", "c"], only_b, "test", False))

    assert dict(pairs) == {"a": None, "b": "ok-b", "c": None}


def test_run_batch_continues_when_one_item_fails():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory)

    async def fail_on_b(page, item):
        if item == "b":
            raise RuntimeError("boom")
        return f"ok-{item}"

    pairs = asyncio.run(scraper._run_batch(["a", "b", "c"], fail_on_b, "test", False))

    assert dict(pairs) == {"a": "ok-a", "c": "ok-c"}


def test_run_batch_returns_empty_for_empty_items():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory)

    assert asyncio.run(scraper._run_batch([], echo_search, "test", False)) == []
    assert factory.browsers == []


def test_run_batch_applies_delay_between_requests():
    factory = FakeBrowserFactory()
    scraper = build_scraper(factory, delay_ms=1500)
    sleeps = []

    async def record_sleep(seconds):
        sleeps.append(seconds)

    scraper._sleep = record_sleep

    asyncio.run(scraper._run_batch(["a", "b", "c"], echo_search, "test", False))

    assert sleeps == [1.5, 1.5]


def test_request_delay_reads_from_env_var(monkeypatch):
    monkeypatch.setenv("RUES_REQUEST_DELAY_MS", "2000")

    assert RuesPlaywrightScraper(logger=FakeLogger())._request_delay_ms == 2000


def test_request_delay_defaults_to_1000ms():
    assert RuesPlaywrightScraper(logger=FakeLogger())._request_delay_ms == 1000


# ── Entradas públicas (T09) ──────────────────────────────────────────────────


def test_search_names_returns_dict_keyed_by_name():
    factory = FakeBrowserFactory(lambda: FakePage(card_html=CARD_HTML))
    scraper = build_scraper(factory)

    result = scraper.search_names(["EMPRESA A SAS"])

    assert result["EMPRESA A SAS"].nit == 900111111


def test_search_names_omits_names_without_result():
    factory = FakeBrowserFactory(lambda: FakePage(card_timeout=True))
    scraper = build_scraper(factory)

    assert scraper.search_names(["EMPRESA A SAS"]) == {}


def test_search_names_deduplicates_and_skips_blank_names():
    factory = FakeBrowserFactory(lambda: FakePage(card_html=CARD_HTML))
    scraper = build_scraper(factory)

    scraper.search_names(["EMPRESA A SAS", "EMPRESA A SAS", "", "   "])

    page = factory.browsers[0].contexts[0].pages[0]
    assert page.locators["input[type='search'], input#search"].filled == [
        "EMPRESA A SAS"
    ]


def test_search_by_name_delegates_to_search_names():
    factory = FakeBrowserFactory(lambda: FakePage(card_html=CARD_HTML))
    scraper = build_scraper(factory)

    result = scraper.search_by_name("EMPRESA A SAS")

    assert result.nit == 900111111
    assert len(factory.browsers) == 1


def test_search_by_name_returns_none_when_not_found():
    factory = FakeBrowserFactory(lambda: FakePage(card_timeout=True))
    scraper = build_scraper(factory)

    assert scraper.search_by_name("EMPRESA A SAS") is None


def test_search_nits_still_returns_list():
    factory = FakeBrowserFactory(lambda: FakePage(card_html=CARD_HTML))
    scraper = build_scraper(factory)

    results = scraper.search_nits(["900111111", "900222222"])

    assert len(results) == 2
    assert all(r.is_company for r in results)


def test_search_nits_uses_single_browser():
    factory = FakeBrowserFactory(lambda: FakePage(card_html=CARD_HTML))
    scraper = build_scraper(factory)

    scraper.search_nits(["900111111", "900222222", "900333333"])

    assert len(factory.browsers) == 1
