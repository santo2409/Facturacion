"""Tests para RUESNitService (writer only, search requires browser)."""
import json

import src.scrapping.infrastructure.console.nit_service as nit_service_module
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo


def test_writer_creates_json_file(tmp_path):
    service = RUESNitService(logger=FakeLogger())
    data = [
        NitResult(nit=900111111, is_company=True, name="EMPRESA A"),
        NitResult(nit=900222222, is_company=False, name=None),
    ]
    file_path = str(tmp_path / "output.json")
    service.writer(data, file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert len(loaded) == 2
    assert loaded[0]["nit"] == 900111111
    assert loaded[0]["name"] == "EMPRESA A"
    assert loaded[1]["name"] is None


def test_search_delegates_to_odoo_fallback_use_case_with_cache():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "EMPRESA ODOO"}})
    cache = FakeNitCacheRepo(cached={"222": NitResult("222", True, "EMPRESA CACHEADA", "BD local")})
    service = RUESNitService(logger=FakeLogger(), odoo_repo=odoo, nit_cache_repo=cache)

    result = service.search(["111", "222"])

    names = sorted(r.name for r in result)
    assert names == ["EMPRESA CACHEADA", "EMPRESA ODOO"]


def test_search_retries_on_transient_scraper_error(monkeypatch):
    monkeypatch.setattr(nit_service_module.time, "sleep", lambda _seconds: None)
    service = RUESNitService(logger=FakeLogger())

    calls = {"count": 0}
    expected = [NitResult("111", True, "EMPRESA OK")]

    def flaky_execute(nits, show_progress=False):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("Fallo transitorio del scraper")
        return expected

    monkeypatch.setattr(service._use_case, "execute", flaky_execute)

    result = service.search(["111"])

    assert result == expected
    assert calls["count"] == 2
