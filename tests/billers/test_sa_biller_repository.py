"""Tests para SaBillerRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.billers.domain.entities.biller import Biller
from src.billers.infrastructure.persistence.sa_biller_company_repository import (
    SaBillerCompanyRepository,
)
from src.billers.infrastructure.persistence.sa_biller_repository import SaBillerRepository
from tests.fakes.fake_logger import FakeLogger


def _mock_session():
    return MagicMock()


def test_all_returns_list_of_dicts():
    session = _mock_session()
    row1 = SimpleNamespace(id=1, name="ALFA")
    row2 = SimpleNamespace(id=2, name="BETA")
    session.query.return_value.all.return_value = [row1, row2]

    repo = SaBillerRepository(session, FakeLogger())
    result = repo.all()
    assert result == [{"id": 1, "name": "ALFA"}, {"id": 2, "name": "BETA"}]


def test_find_by_name_found():
    session = _mock_session()
    row = SimpleNamespace(id=1, name="ALFA")
    session.query.return_value.filter_by.return_value.first.return_value = row

    repo = SaBillerRepository(session, FakeLogger())
    result = repo.find_by_name("ALFA")
    assert result == (1, "ALFA")


def test_find_by_name_not_found():
    session = _mock_session()
    session.query.return_value.filter_by.return_value.first.return_value = None

    repo = SaBillerRepository(session, FakeLogger())
    assert repo.find_by_name("NOPE") is None


def test_save_batch_commits():
    session = _mock_session()
    session.execute.return_value.fetchall.return_value = [(1, "A"), (2, "B")]

    repo = SaBillerRepository(session, FakeLogger())
    result = repo.save_batch([Biller("A"), Biller("B")])
    assert len(result) == 2
    session.commit.assert_called_once()


def test_save_batch_empty():
    session = _mock_session()
    repo = SaBillerRepository(session, FakeLogger())
    assert repo.save_batch([]) == []


def test_save_batch_rollback_on_error():
    session = _mock_session()
    session.execute.side_effect = Exception("DB error")

    repo = SaBillerRepository(session, FakeLogger())
    result = repo.save_batch([Biller("A")])
    assert result == []
    session.rollback.assert_called_once()


def test_all_returns_none_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    repo = SaBillerRepository(session, FakeLogger())
    assert repo.all() is None


# AUD-42: una lectura fallida deja la sesión compartida usable (rollback) y devuelve None.
def test_all_rolls_back_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    assert SaBillerRepository(session, FakeLogger()).all() is None
    session.rollback.assert_called_once()


def test_find_by_name_rolls_back_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    assert SaBillerRepository(session, FakeLogger()).find_by_name("ALFA") is None
    session.rollback.assert_called_once()


def test_biller_company_all_rolls_back_on_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    assert SaBillerCompanyRepository(session, FakeLogger()).all() is None
    session.rollback.assert_called_once()
