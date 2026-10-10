import pytest

from src.shared.logging.infrastructure.logging.tech_only_logger import TechOnlyLogger


class RecordingLogger:
    """Doble local que sí registra `user_msg` (FakeLogger lo descarta)."""

    def __init__(self):
        self.calls = []

    def _record(self, level, message, exc_info=None, user_msg=None):
        self.calls.append({"level": level, "message": message, "exc_info": exc_info, "user_msg": user_msg})

    def debug(self, message, *, user_msg=None):
        self._record("debug", message, user_msg=user_msg)

    def info(self, message, *, user_msg=None):
        self._record("info", message, user_msg=user_msg)

    def warning(self, message, *, user_msg=None):
        self._record("warning", message, user_msg=user_msg)

    def error(self, message, exc_info=None, *, user_msg=None):
        self._record("error", message, exc_info, user_msg)

    def critical(self, message, exc_info=None, *, user_msg=None):
        self._record("critical", message, exc_info, user_msg)


def test_user_msg_is_not_forwarded():
    inner = RecordingLogger()

    TechOnlyLogger(inner).info("técnico", user_msg="para el usuario")

    assert inner.calls == [{"level": "info", "message": "técnico", "exc_info": None, "user_msg": None}]


def test_message_and_exc_info_are_forwarded():
    inner = RecordingLogger()
    boom = ValueError("x")

    TechOnlyLogger(inner).error("falló", exc_info=boom, user_msg="no se envía")

    assert inner.calls[0]["message"] == "falló"
    assert inner.calls[0]["exc_info"] is boom
    assert inner.calls[0]["user_msg"] is None


@pytest.mark.parametrize("level", ["debug", "info", "warning", "error", "critical"])
def test_all_levels_supported(level):
    inner = RecordingLogger()

    getattr(TechOnlyLogger(inner), level)("m", user_msg="u")

    assert [c["level"] for c in inner.calls] == [level]
    assert inner.calls[0]["user_msg"] is None
