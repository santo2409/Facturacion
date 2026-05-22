"""Tests para SaActivityRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.activity.infrastructure.sa_activity_type_repository import SaActivityRepository
from tests.fakes.fake_logger import FakeLogger


def test_all_returns_list():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="INTRA")
    session.query.return_value.all.return_value = [row]

    repo = SaActivityRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "INTRA"}]


def test_find_by_name_found():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="INTRA")
    session.query.return_value.filter_by.return_value.first.return_value = row

    repo = SaActivityRepository(session, FakeLogger())
    assert repo.find_by_name("INTRA") == (1, "INTRA")


def test_find_by_name_not_found():
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None

    repo = SaActivityRepository(session, FakeLogger())
    assert repo.find_by_name("NOPE") is None
