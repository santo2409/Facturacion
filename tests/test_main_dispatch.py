"""Tests para el dispatch seguro del menú principal (spec 007, RF-09).
Una excepción no controlada de una opción no debe terminar el proceso: se
registra, se informa y el menú continúa."""

import main
from tests.fakes.fake_logger import FakeLogger


def test_safe_dispatch_captura_excepcion_y_continua(monkeypatch):
    def _raising_dispatch(option, logger):
        raise RuntimeError("fallo simulado en la opción")

    monkeypatch.setattr(main, "dispatch_option", _raising_dispatch)
    logger = FakeLogger()

    result = main.safe_dispatch("1", logger)  # no debe propagar RuntimeError

    assert result is True
    assert logger.errors


def test_safe_dispatch_propaga_el_resultado_de_dispatch_option(monkeypatch):
    monkeypatch.setattr(main, "dispatch_option", lambda option, logger: False)
    logger = FakeLogger()

    result = main.safe_dispatch("0", logger)

    assert result is False
    assert not logger.errors
