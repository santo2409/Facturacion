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
