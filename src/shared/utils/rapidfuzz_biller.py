from rapidfuzz import fuzz, process
from unidecode import unidecode

from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class RapidFuzzBiller:
    def __init__(self, logger: LoggerAdapter = None):
        self.logger = logger or LoggerAdapter(__name__)

    def fuzz_property(self, property_name: str, catalog: list[dict]) -> str | None:
        try:
            property_norm = unidecode(property_name.strip().upper())

            # Extraemos solo los nombres
            names = [item["name"] for item in catalog]

            scorers = (
                fuzz.token_sort_ratio,
                fuzz.partial_ratio,
            )

            for scorer in scorers:
                match, score, idx = process.extractOne(
                    property_norm, names, scorer=scorer
                )

                if score >= 90:
                    return catalog[idx]["name"]

            return None

        except Exception as excep:
            self.logger.error(f"Error in fuzz_property: {excep}", exc_info=True, user_msg="Error al buscar coincidencias. El proceso continuará sin esta validación.")
