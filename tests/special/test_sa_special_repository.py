"""Tests para SaSpecialRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.special.domain.entities.special import Special
from src.special.infrastructure.persistence.sa_special_repository import SaSpecialRepository
from tests.fakes.fake_logger import FakeLogger


def test_all_returns_list():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="ESPECIAL A")
    session.query.return_value.all.return_value = [row]

    repo = SaSpecialRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "ESPECIAL A"}]


def test_save_batch_commits():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [(1, "SPEC")]

    repo = SaSpecialRepository(session, FakeLogger())
    result = repo.save_batch([Special("SPEC")])
    assert len(result) == 1
    session.commit.assert_called_once()
