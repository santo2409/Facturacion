import logging


class LoggerAdapter:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def error(self, message: str, exc_info=None) -> None:
        self._logger.error(message, exc_info=exc_info)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)
