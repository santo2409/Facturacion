"""Tests para SaPackageRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.package.domain.entities.package import Package
from src.package.infrastructure.persistence.sa_package_repository import SaPackageRepository
from tests.fakes.fake_logger import FakeLogger


def test_all_returns_list():
    session = MagicMock()
    row = SimpleNamespace(id=1, name="PAQUETE BASICO")
    session.query.return_value.all.return_value = [row]

    repo = SaPackageRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "PAQUETE BASICO"}]


def test_save_batch_commits():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [(1, "PKG")]

    repo = SaPackageRepository(session, FakeLogger())
    result = repo.save_batch([Package("PKG")])
    assert len(result) == 1
    session.commit.assert_called_once()


def test_save_batch_rollback_on_error():
    session = MagicMock()
    session.execute.side_effect = Exception("DB error")

    repo = SaPackageRepository(session, FakeLogger())
    result = repo.save_batch([Package("PKG")])
    assert result == []
    session.rollback.assert_called_once()
