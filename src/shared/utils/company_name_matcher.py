from src.shared.utils.text_normalizer import normalize_company_name


class CompanyNameMatcher:
    """Valida una coincidencia de razón social contra un umbral difuso y
    devuelve el candidato completo, no solo su nombre."""

    def __init__(self, fuzz, threshold: int = 90):
        self._fuzz = fuzz
        self._threshold = threshold

    @staticmethod
    def _normalize(text: str) -> str:
        return normalize_company_name(text)

    def best_match(
        self, expected_name: str, candidates: list[dict], name_key: str = "name"
    ) -> dict | None:
        expected = self._normalize(expected_name)
        if not expected or not candidates:
            return None

        index: dict[str, dict] = {}
        for candidate in candidates:
            key = self._normalize(candidate.get(name_key) or "")
            if key and key not in index:
                index[key] = candidate
        if not index:
            return None

        winner = self._fuzz.fuzz_property(
            expected, [{"name": key} for key in index], threshold=self._threshold
        )
        return index.get(winner) if winner else None
