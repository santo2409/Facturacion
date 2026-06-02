import unicodedata

from rapidfuzz import fuzz, process

from src.odooInjection.domain.entities.city_account_map import (
    CIUDAD_CUENTA,
    CUENTA_ANALITICA_FALLBACK,
)

UMBRAL_FUZZY = 80


def _normalize(s: str) -> str:
    s = s.upper().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


_CIUDAD_CUENTA_NORM = {_normalize(k): v for k, v in CIUDAD_CUENTA.items()}
_CLAVES_NORM = list(_CIUDAD_CUENTA_NORM.keys())


class CityAccountResolver:
    def resolve(self, ciudad_raw: str | None) -> tuple[str, str | None, int]:
        """Retorna (cuenta_analitica, ciudad_match, score)."""
        if not ciudad_raw:
            return CUENTA_ANALITICA_FALLBACK, None, 0
        ciudad_norm = _normalize(str(ciudad_raw))
        if ciudad_norm in _CIUDAD_CUENTA_NORM:
            return _CIUDAD_CUENTA_NORM[ciudad_norm], ciudad_raw, 100
        resultado = process.extractOne(ciudad_norm, _CLAVES_NORM, scorer=fuzz.WRatio)
        if resultado and resultado[1] >= UMBRAL_FUZZY:
            return _CIUDAD_CUENTA_NORM[resultado[0]], resultado[0], resultado[1]
        return CUENTA_ANALITICA_FALLBACK, None, 0
