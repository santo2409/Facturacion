"""Pruebas de SaBillingRedirectRepository con una sesión falsa (sin mocks)."""
from types import SimpleNamespace

from src.company.infrastructure.persistence.sa_billing_redirect_repository import (
    SaBillingRedirectRepository,
)
from tests.fakes.fake_logger import FakeLogger


class _SesionFalsa:
    def __init__(self, filas=None, error=None):
        self._filas = filas or []
        self._error = error
        self.filtros = 0
        self.rollbacks = 0

    def query(self, _modelo):
        if self._error:
            raise self._error
        return self

    def filter(self, *_):
        self.filtros += 1
        return self

    def all(self):
        return list(self._filas)

    def rollback(self):
        self.rollbacks += 1


def test_redirects_all_devuelve_dicts_filtrando_borrados():
    fila = SimpleNamespace(nit_origen="800082633", nit_destino="901555555", etiqueta="OTRA", name="LAB")
    sesion = _SesionFalsa([fila])

    result = SaBillingRedirectRepository(sesion, FakeLogger()).all()

    assert result == [{"nit_origen": "800082633", "nit_destino": "901555555", "etiqueta": "OTRA", "name": "LAB"}]
    assert sesion.filtros == 1


def test_redirects_all_rollback_y_lista_vacia_en_error():
    sesion = _SesionFalsa(error=Exception("DB error"))
    logger = FakeLogger()

    result = SaBillingRedirectRepository(sesion, logger).all()

    assert result == []
    assert sesion.rollbacks == 1
    assert logger.errors


# ── upsert y desactivación contra una base real (SQLite en memoria) ──────────
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.shared.database.models import BillingRedirectModel  # noqa: E402


def _sesion_sqlite():
    engine = create_engine("sqlite://")
    BillingRedirectModel.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_redirects_upsert_crea_actualiza_y_reactiva():
    sesion = _sesion_sqlite()
    repo = SaBillingRedirectRepository(sesion, FakeLogger())
    fila = {"nit_origen": "101907357", "nit_destino": "860507033", "etiqueta": "VISE", "name": "DEAS"}

    assert repo.upsert_many([fila]) == (1, 0)
    assert repo.deactivate(["101907357", "555555555"]) == ["101907357"]
    assert repo.all() == []
    assert repo.upsert_many([{**fila, "etiqueta": "VISE2"}]) == (0, 1)
    assert repo.all() == [{**fila, "etiqueta": "VISE2"}]


def test_redirects_upsert_si_falla_no_guarda_nada():
    sesion = _sesion_sqlite()
    logger = FakeLogger()
    repo = SaBillingRedirectRepository(sesion, logger)
    filas = [{"nit_origen": "1", "nit_destino": "2", "etiqueta": "A", "name": None},
             {"nit_origen": "3", "nit_destino": None, "etiqueta": "B", "name": None}]   # NOT NULL falla
    assert repo.upsert_many(filas) is None
    assert repo.all() == [] and logger.errors
