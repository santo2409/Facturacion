"""Tests de la lógica pura de RuesPlaywrightScraper (sin red ni browser)."""
import math

import pytest

from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    DEFAULT_CONCURRENCY,
    MAX_CONCURRENCY,
    RuesPlaywrightScraper,
)
from tests.fakes.fake_logger import FakeLogger


def test_prepare_nits_filters_none_and_nan():
    scraper = RuesPlaywrightScraper(logger=FakeLogger())

    result = scraper._prepare_nits([["111"], [None], [math.nan], ["222"]])

    assert result == [111, 222]


def test_prepare_nits_logs_and_skips_invalid_values():
    logger = FakeLogger()
    scraper = RuesPlaywrightScraper(logger=logger)

    result = scraper._prepare_nits([["abc"], ["111"]])

    assert result == [111]
    assert logger.errors


def test_prepare_nits_accepts_flat_list():
    scraper = RuesPlaywrightScraper(logger=FakeLogger())

    result = scraper._prepare_nits(["111", "222"])

    assert result == [111, 222]


def test_prepare_nits_accepts_single_scalar():
    scraper = RuesPlaywrightScraper(logger=FakeLogger())

    result = scraper._prepare_nits("111")

    assert result == [111]


@pytest.mark.parametrize(
    "items,n,expected_chunk_count",
    [
        ([], 3, 0),
        ([1, 2], 3, 2),
        ([1, 2, 3, 4, 5], 2, 2),
    ],
)
def test_split_never_returns_empty_chunks(items, n, expected_chunk_count):
    chunks = RuesPlaywrightScraper._split(items, n)

    assert len(chunks) == expected_chunk_count
    assert all(chunk for chunk in chunks)
    assert sorted(x for chunk in chunks for x in chunk) == sorted(items)


def test_default_concurrency_is_one():
    scraper = RuesPlaywrightScraper(logger=FakeLogger())
    assert scraper.concurrency == DEFAULT_CONCURRENCY
    assert scraper.concurrency == 1


def test_concurrency_is_clamped_to_max():
    scraper = RuesPlaywrightScraper(logger=FakeLogger(), concurrency=20)
    assert scraper.concurrency == MAX_CONCURRENCY


def test_concurrency_is_clamped_to_at_least_one():
    scraper = RuesPlaywrightScraper(logger=FakeLogger(), concurrency=0)
    assert scraper.concurrency == 1


def test_concurrency_reads_from_env_var(monkeypatch):
    monkeypatch.setenv("RUES_SCRAPER_CONCURRENCY", "2")
    scraper = RuesPlaywrightScraper(logger=FakeLogger())
    assert scraper.concurrency == 2


def test_explicit_concurrency_overrides_env_var(monkeypatch):
    monkeypatch.setenv("RUES_SCRAPER_CONCURRENCY", "2")
    scraper = RuesPlaywrightScraper(logger=FakeLogger(), concurrency=4)
    assert scraper.concurrency == 4


def test_result_timeout_defaults_to_10000ms():
    scraper = RuesPlaywrightScraper(logger=FakeLogger())
    assert scraper._result_timeout_ms == 10000


def test_result_timeout_reads_from_env_var(monkeypatch):
    monkeypatch.setenv("RUES_RESULT_TIMEOUT_MS", "7000")
    scraper = RuesPlaywrightScraper(logger=FakeLogger())
    assert scraper._result_timeout_ms == 7000
