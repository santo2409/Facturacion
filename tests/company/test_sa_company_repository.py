"""Tests para SaCompanyRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.company.domain.entities.company import Company
from src.company.infrastructure.persistence.sa_company_repository import SaCompanyRepository
from tests.fakes.fake_logger import FakeLogger


def _mock_session():
    return MagicMock()


def test_all_returns_list():
    session = _mock_session()
    row = SimpleNamespace(id=1, nit="900111111", name="empresa a")
    session.query.return_value.all.return_value = [row]

    repo = SaCompanyRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "nit": "900111111", "name": "EMPRESA A"}]


def test_find_by_nit_found():
    session = _mock_session()
    row = SimpleNamespace(id=1, nit="900111111", name="A")
    session.query.return_value.filter_by.return_value.first.return_value = row

    repo = SaCompanyRepository(session, FakeLogger())
    assert repo.find_by_nit("900111111") == (1, "900111111", "A")


def test_find_by_nit_not_found():
    session = _mock_session()
    session.query.return_value.filter_by.return_value.first.return_value = None

    repo = SaCompanyRepository(session, FakeLogger())
    assert repo.find_by_nit("999") is None


def test_save_batch_commits():
    session = _mock_session()
    session.execute.return_value.fetchall.return_value = [(1, "900111111", "A")]

    repo = SaCompanyRepository(session, FakeLogger())
    result = repo.save_batch([Company("900111111", "A")])
    assert len(result) == 1
    session.commit.assert_called_once()


def test_save_batch_rollback_on_error():
    session = _mock_session()
    session.execute.side_effect = Exception("DB error")

    repo = SaCompanyRepository(session, FakeLogger())
    result = repo.save_batch([Company("900111111", "A")])
    assert result == []
    session.rollback.assert_called_once()


def test_all_rollback_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("column companies.verified_at does not exist")

    repo = SaCompanyRepository(session, FakeLogger())
    result = repo.all()
    assert result is None
    session.rollback.assert_called_once()


def test_find_by_nit_rollback_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    repo = SaCompanyRepository(session, FakeLogger())
    result = repo.find_by_nit("900111111")
    assert result is None
    session.rollback.assert_called_once()
