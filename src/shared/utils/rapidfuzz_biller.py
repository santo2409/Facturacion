from rapidfuzz import fuzz, process
from unidecode import unidecode

from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class RapidFuzzBiller:
    _USER_ERROR_MSG = "Error al buscar coincidencias. El proceso continuará sin esta validación."

    def __init__(self, logger: LoggerAdapter = None):
        self.logger = logger or LoggerAdapter(__name__)
        self._empty_catalog_warned = False

    def fuzz_property(self, property_name: str, catalog: list[dict], threshold: int = 90) -> str | None:
        try:
            property_norm = unidecode(property_name.strip().upper())

            # Extraemos solo los nombres
            names = [item["name"] for item in catalog]
            if not names:
                # Catálogo vacío: sin coincidencia posible. Se avisa una vez por
                # ejecución, no una vez por fila (AUD-66).
                if not self._empty_catalog_warned:
                    self._empty_catalog_warned = True
                    self.logger.error(
                        "fuzz_property con catálogo vacío", user_msg=self._USER_ERROR_MSG
                    )
                return None

            scorers = (
                fuzz.token_sort_ratio,
                fuzz.partial_ratio,
            )

            for scorer in scorers:
                match, score, idx = process.extractOne(
                    property_norm, names, scorer=scorer
                )

                if score >= threshold:
                    return catalog[idx]["name"]

            return None

        except Exception as excep:
            self.logger.error(f"Error in fuzz_property: {excep}", exc_info=True, user_msg=self._USER_ERROR_MSG)

    def similarity(self, a: str, b: str) -> int:
        """Puntaje 0-100 de parecido entre dos textos ya normalizados por el llamador."""
        try:
            return int(fuzz.token_sort_ratio(a, b))
        except Exception as excep:
            self.logger.error(f"Error in similarity: {excep}", exc_info=True)
            return 0
