class TechOnlyLogger:
    """Decorador de `LoggerAdapter` que descarta `user_msg`.

    Se inyecta en las dependencias compartidas de un flujo que tiene su propia
    salida al usuario (resumen en consola y libros por ejecución), para que sus
    repositorios no dupliquen mensajes en la consola, sin tocar cada uno.
    """

    def __init__(self, logger):
        self._logger = logger

    def debug(self, message: str, *, user_msg: str | None = None) -> None:
        self._logger.debug(message)

    def info(self, message: str, *, user_msg: str | None = None) -> None:
        self._logger.info(message)

    def warning(self, message: str, *, user_msg: str | None = None) -> None:
        self._logger.warning(message)

    def error(self, message: str, exc_info=None, *, user_msg: str | None = None) -> None:
        self._logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info=None, *, user_msg: str | None = None) -> None:
        self._logger.critical(message, exc_info=exc_info)
