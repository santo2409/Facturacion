"""Tests de la config de logging sin user_audit.xlsx (spec 011, AC-01 y AC-02).

setup_logging() muta estado global (dictConfig, guard del logger raíz y
atributos de clase de LoggerAdapter): el fixture lo aísla y lo restaura para
no contaminar el resto de la suite."""

import logging
from io import StringIO

import pytest

from src.shared.console.user_console import USER_CONSOLE
from src.shared.logging.config import logging_config  # noqa: F401  (carga .env antes de fijar DIRECTORY)
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.logging.spec import root_logger_guard
from src.shared.logging.spec.spec_loader import SpecLoader

_HANDLER_FACTORY = "src.shared.console.user_console.build_user_console_handler"


@pytest.fixture
def isolated_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(USER_CONSOLE, "file", StringIO())

    root = logging.getLogger()
    saved_root = {k: root.__dict__[k] for k in ("addHandler", "setLevel") if k in root.__dict__}
    saved_guard = dict(root_logger_guard._originals)
    saved_adapter = (LoggerAdapter._user_logger, set(LoggerAdapter._allowed_levels))
    saved_handlers = {
        name: logging.getLogger(name).handlers[:] for name in ("user_logger", "tech_logger")
    }

    # `import main` (tests/test_main_dispatch.py) ya instaló el guard al coleccionar;
    # instalarlo dos veces lo envuelve a sí mismo y recursa, así que se parte de limpio.
    root_logger_guard.uninstall()

    yield tmp_path

    for name, handlers in saved_handlers.items():
        lg = logging.getLogger(name)
        for h in lg.handlers:
            if h not in handlers:
                h.close()
        lg.handlers = handlers
    for key in ("addHandler", "setLevel"):
        root.__dict__.pop(key, None)
    root.__dict__.update(saved_root)
    root_logger_guard._originals.clear()
    root_logger_guard._originals.update(saved_guard)
    LoggerAdapter._user_logger, LoggerAdapter._allowed_levels = saved_adapter


def test_setup_logging_does_not_create_user_audit_xlsx(isolated_logging):
    logging_config.setup_logging()

    LoggerAdapter("cualquier_modulo").info("técnico", user_msg="mensaje de usuario")

    handler_names = [type(h).__name__ for h in logging.getLogger("user_logger").handlers]
    assert "ExcelAuditHandler" not in handler_names
    assert not (isolated_logging / "logs" / "user_audit.xlsx").exists()


def test_user_msg_is_rendered_on_user_console_with_level(isolated_logging):
    logging_config.setup_logging()

    LoggerAdapter("cualquier_modulo").warning("técnico", user_msg="Revisa la ciudad")

    output = USER_CONSOLE.file.getvalue()
    assert "Revisa la ciudad" in output
    assert "WARNING" in output
    assert "técnico" not in output


def test_technical_message_still_goes_to_logs_log(isolated_logging):
    logging_config.setup_logging()

    LoggerAdapter("tech_logger").info("mensaje técnico persistente", user_msg="para la consola")

    assert "mensaje técnico persistente" in (isolated_logging / "logs.log").read_text(encoding="utf-8")


def test_fallback_spec_uses_same_console_handler():
    fallback = SpecLoader().load(path="__fallback__")["config"]
    yaml_spec = SpecLoader().load()["config"]

    assert fallback["handlers"]["console"]["()"] == _HANDLER_FACTORY
    assert yaml_spec["handlers"]["console"]["()"] == _HANDLER_FACTORY
    assert fallback["loggers"]["user_logger"]["handlers"] == ["console"]
    assert yaml_spec["loggers"]["user_logger"]["handlers"] == ["console"]


def test_no_configured_handler_is_excel_audit_handler():
    for config in (SpecLoader().load()["config"], SpecLoader().load(path="__fallback__")["config"]):
        assert "excel" not in config["handlers"]
        assert all("ExcelAuditHandler" not in str(h) for h in config["handlers"].values())


def test_excel_audit_handler_module_no_longer_exists():
    import importlib.util

    spec = importlib.util.find_spec(
        "src.shared.logging.infrastructure.logging.excel_audit_handler"
    )

    assert spec is None
