"""Tests para SaCityRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.city.domain.entities.city import City
from src.city.infrastructure.persistence.sa_city_repository import SaCityRepository
from tests.fakes.fake_logger import FakeLogger


def test_all_returns_list():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="BOGOTA")
    session.query.return_value.all.return_value = [row]

    repo = SaCityRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "BOGOTA"}]


def test_save_batch_commits():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [(1, "BOGOTA")]

    repo = SaCityRepository(session, FakeLogger())
    result = repo.save_batch([City("BOGOTA")])
    assert len(result) == 1
    session.commit.assert_called_once()
