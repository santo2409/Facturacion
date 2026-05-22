"""Tests para RUESNitService (writer only, search requires browser)."""
import json

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from tests.fakes.fake_logger import FakeLogger


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
