"""Tests para SaImedicalRepository con mock de Session."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.company.domain.entities.imedical_correction import ImedicalCorrection
from src.company.infrastructure.persistence.sa_imedical_repository import SaImedicalRepository
from tests.fakes.fake_logger import FakeLogger


def _mock_session():
    return MagicMock()


def test_all_filtra_registros_con_deleted_at():
    """all() debe consultar solo filas no borradas (deleted_at IS NULL)."""
    session = _mock_session()
    row = SimpleNamespace(
        nit_error="1015426422", name="KONRAD LORENZ", nit_success="860504759", name_error="KL SAS"
    )
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaImedicalRepository(session, FakeLogger())
    result = repo.all()

    assert result == [{
        "nit_error": "1015426422",
        "name": "KONRAD LORENZ",
        "nit_success": "860504759",
        "name_error": "KL SAS",
    }]
    session.query.return_value.filter.assert_called_once()


def test_all_devuelve_dicts_no_objetos_orm():
    session = _mock_session()
    row = SimpleNamespace(nit_error="1", name="X", nit_success="2", name_error=None)
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaImedicalRepository(session, FakeLogger())
    result = repo.all()

    assert isinstance(result[0], dict)


def test_save_batch_hace_upsert_por_nit_error():
    session = _mock_session()
    repo = SaImedicalRepository(session, FakeLogger())

    n = repo.save_batch([
        ImedicalCorrection(nit_error="1015426422", nit_success="860504759", name="X", name_error="Y")
    ])

    assert n == 1
    session.execute.assert_called_once()
    session.commit.assert_called_once()


def test_save_batch_guarda_nit_error_crudo_tal_cual_se_paso():
    """El repo no debe truncar ni transformar nit_error: eso es responsabilidad del caller (AC-09)."""
    session = _mock_session()
    repo = SaImedicalRepository(session, FakeLogger())

    correction = ImedicalCorrection(
        nit_error="10154264220", nit_success="860504759", name="X", name_error="Y"
    )
    repo.save_batch([correction])

    stmt = session.execute.call_args[0][0]
    values = stmt.compile().params
    assert values["nit_error_m0"] == "10154264220"


def test_save_batch_hace_rollback_y_loguea_en_error():
    session = _mock_session()
    session.execute.side_effect = Exception("DB error")

    repo = SaImedicalRepository(session, FakeLogger())
    n = repo.save_batch([
        ImedicalCorrection(nit_error="1", nit_success="2", name="X")
    ])

    assert n == 0
    session.rollback.assert_called_once()


def test_save_batch_lista_vacia_no_toca_la_sesion():
    session = _mock_session()
    repo = SaImedicalRepository(session, FakeLogger())

    n = repo.save_batch([])

    assert n == 0
    session.execute.assert_not_called()
    session.commit.assert_not_called()
