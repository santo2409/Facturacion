"""Tests para SaTianRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.company.infrastructure.persistence.sa_tian_repository import SaTianRepository
from tests.fakes.fake_logger import FakeLogger


def _mock_session():
    return MagicMock()


def test_all_filtra_registros_con_deleted_at():
    session = _mock_session()
    row = SimpleNamespace(nit_error="800082633", name="LABORATORIOS DERMANAT S.A.S")
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaTianRepository(session, FakeLogger())
    result = repo.all()

    assert result == [{"nit_error": "800082633", "name": "LABORATORIOS DERMANAT S.A.S"}]
    session.query.return_value.filter.assert_called_once()


def test_all_devuelve_dicts_no_objetos_orm():
    session = _mock_session()
    row = SimpleNamespace(nit_error="1", name="X")
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaTianRepository(session, FakeLogger())
    result = repo.all()

    assert isinstance(result[0], dict)


def test_all_rollback_y_lista_vacia_en_error():
    session = _mock_session()
    session.query.side_effect = Exception("DB error")

    repo = SaTianRepository(session, FakeLogger())
    result = repo.all()

    assert result == []
    session.rollback.assert_called_once()
