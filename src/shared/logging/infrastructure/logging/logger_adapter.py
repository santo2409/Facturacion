import logging
import warnings


class LoggerAdapter:
    _allowed_levels: set = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    _user_logger: logging.Logger | None = None

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    @classmethod
    def configure(cls, allowed_levels: list):
        cls._allowed_levels = set(allowed_levels)
        cls._user_logger = logging.getLogger("user_logger")

    def _check(self, level: str) -> bool:
        if level not in self._allowed_levels:
            warnings.warn(f"Log level '{level}' not in allowed_levels, skipping", stacklevel=3)
            return False
        return True

    def _forward_user(self, level: str, user_msg: str | None):
        if user_msg and self._user_logger and self._logger.name != "user_logger":
            getattr(self._user_logger, level.lower())(user_msg)

    def debug(self, message: str, *, user_msg: str | None = None) -> None:
        if self._check("DEBUG"):
            self._logger.debug(message)
            self._forward_user("DEBUG", user_msg)

    def info(self, message: str, *, user_msg: str | None = None) -> None:
        if self._check("INFO"):
            self._logger.info(message)
            self._forward_user("INFO", user_msg)

    def warning(self, message: str, *, user_msg: str | None = None) -> None:
        if self._check("WARNING"):
            self._logger.warning(message)
            self._forward_user("WARNING", user_msg)

    def error(self, message: str, exc_info=None, *, user_msg: str | None = None) -> None:
        if self._check("ERROR"):
            self._logger.error(message, exc_info=exc_info)
            self._forward_user("ERROR", user_msg)

    def critical(self, message: str, exc_info=None, *, user_msg: str | None = None) -> None:
        if self._check("CRITICAL"):
            self._logger.critical(message, exc_info=exc_info)
            self._forward_user("CRITICAL", user_msg)
