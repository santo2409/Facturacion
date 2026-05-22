"""Tests para SaProviderRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.provider.domain.entities.provider import Provider
from src.provider.infrastructure.persistence.sa_provider_repository import SaProviderRepository
from tests.fakes.fake_logger import FakeLogger


def test_all_returns_list():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="PROVEEDOR X")
    session.query.return_value.all.return_value = [row]

    repo = SaProviderRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "PROVEEDOR X"}]


def test_save_batch_commits():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [(1, "PROV")]

    repo = SaProviderRepository(session, FakeLogger())
    result = repo.save_batch([Provider("PROV")])
    assert len(result) == 1
    session.commit.assert_called_once()
