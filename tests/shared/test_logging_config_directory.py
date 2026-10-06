"""Tests para la resolución de DIRECTORY en logging_config.py (spec 007,
RF-07). El valor por defecto de este módulo ya coincidía con
DEFAULT_DIRECTORY ("."), así que el defecto no es un crash sino la
duplicación del literal en dos sitios: se verifica que ahora hay una sola
fuente de verdad.

No se llama a setup_logging() en este test: parchea el logger raíz de
forma global (`root_logger_guard.py`) y ningún test del repo lo invoca por
ese motivo — llamarlo aquí contaminaría el estado global del logging para
el resto de la suite."""

import inspect

from src.shared.logging.config import logging_config


def test_logging_config_no_usa_os_getenv_directory_directo():
    source = inspect.getsource(logging_config)

    assert 'os.getenv("DIRECTORY"' not in source
    assert "get_paths_config" in source
