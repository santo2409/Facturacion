"""AUD-11: con ODOO_TIMEOUT_SECONDS inválido la opción 6 se detiene con un mensaje."""

import pytest

from src.assign.infrastructure.console import assigned_rates_controller as ctrl


class _LoggerGrabador:
    def __init__(self):
        self.user_msgs = []

    def error(self, msg, *a, user_msg=None, **k):
        if user_msg:
            self.user_msgs.append(user_msg)

    def __getattr__(self, name):
        return lambda *a, **k: None


def _no_llamar(*a, **k):
    pytest.fail("la opción debía detenerse antes")


@pytest.mark.parametrize("with_invoices", [False, True])
def test_assign_rates_stops_on_invalid_odoo_timeout(monkeypatch, with_invoices):
    monkeypatch.setenv("ODOO_TIMEOUT_SECONDS", "abc")
    monkeypatch.setattr(ctrl, "ask_excel_path", _no_llamar)
    monkeypatch.setattr(ctrl, "get_session", _no_llamar)
    logger = _LoggerGrabador()

    assert ctrl.assign_rates(logger, with_invoices=with_invoices) is None

    assert logger.user_msgs == ["La variable de entorno ODOO_TIMEOUT_SECONDS debe ser un número entero."]
