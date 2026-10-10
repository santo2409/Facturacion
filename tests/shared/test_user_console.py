import logging
from io import StringIO

from src.shared.console.progress import RichProgress
from src.shared.console.user_console import USER_CONSOLE, build_user_console_handler


def _logger_with_handler(monkeypatch, level=logging.INFO):
    monkeypatch.setattr(USER_CONSOLE, "file", StringIO())
    handler = build_user_console_handler()
    handler.setLevel(level)
    logger = logging.getLogger("test_user_console")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger


def test_progress_and_log_handler_share_the_same_console():
    progress = RichProgress()("tarea", total=1)

    assert progress.progress.console is USER_CONSOLE
    assert build_user_console_handler().console is USER_CONSOLE


def test_handler_prints_message_with_level(monkeypatch):
    logger = _logger_with_handler(monkeypatch)

    logger.warning("Revisa la ciudad")

    output = USER_CONSOLE.file.getvalue()
    assert "Revisa la ciudad" in output
    assert "WARNING" in output


def test_debug_is_filtered_by_handler_level(monkeypatch):
    logger = _logger_with_handler(monkeypatch, level=logging.INFO)

    logger.debug("no debe verse")

    assert "no debe verse" not in USER_CONSOLE.file.getvalue()
