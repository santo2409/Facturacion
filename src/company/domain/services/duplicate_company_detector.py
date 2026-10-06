import re
from collections import defaultdict
from itertools import combinations

from src.company.domain.entities.duplicate_candidate import DuplicateCandidate
from src.shared.utils.text_normalizer import normalize_company_name

REASON_SAME_NAME = "Nombre idéntico (ignorando puntuación y espacios)"
REASON_NIT_SUFFIX = "NIT difiere en el dígito final"
DEFAULT_SIMILARITY_THRESHOLD = 85

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9Ñ]")


class DuplicateCompanyDetector:
    """Detecta candidatos a empresa duplicada con dos reglas deterministas.

    Se descartó el matching difuso general (RapidFuzz sobre todos los pares)
    porque, medido contra datos reales, producía 14 falsos positivos por cada
    duplicado real — las convenciones de nombres colombianas (consorcios
    numerados, torres, fondos de empleados) hacen que nombres muy similares
    correspondan sistemáticamente a entidades distintas.
    """

    def __init__(self, fuzz, similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD):
        self._fuzz = fuzz
        self._threshold = similarity_threshold

    @staticmethod
    def _clave_agresiva(name: str) -> str:
        return _NON_ALNUM_RE.sub("", normalize_company_name(name))

    def detect(self, companies: list[dict]) -> list[DuplicateCandidate]:
        motivos: dict[tuple[str, str], set[str]] = defaultdict(set)
        por_nit: dict[str, dict] = {}
        for c in companies:
            if c.get("name") and c.get("nit"):
                por_nit[c["nit"]] = c

        self._regla_a(companies, motivos)
        similitudes = self._regla_b(por_nit, motivos)

        pares_ordenados = sorted(motivos.items())
        return [
            DuplicateCandidate(
                nit_a=nit_a,
                name_a=por_nit[nit_a]["name"],
                nit_b=nit_b,
                name_b=por_nit[nit_b]["name"],
                reasons=sorted(reasons),
                similarity=similitudes.get((nit_a, nit_b), 0),
            )
            for (nit_a, nit_b), reasons in pares_ordenados
        ]

    def _regla_a(self, companies, motivos: dict[tuple[str, str], set[str]]) -> None:
        por_clave: dict[str, list[dict]] = defaultdict(list)
        for c in companies:
            if not c.get("name"):
                continue
            clave = self._clave_agresiva(c["name"])
            if clave:
                por_clave[clave].append(c)

        for grupo in por_clave.values():
            if len(grupo) < 2:
                continue
            for a, b in combinations(grupo, 2):
                if a["nit"] == b["nit"]:
                    continue
                par = tuple(sorted([a["nit"], b["nit"]]))
                motivos[par].add(REASON_SAME_NAME)

    def _regla_b(
        self, por_nit: dict[str, dict], motivos: dict[tuple[str, str], set[str]]
    ) -> dict[tuple[str, str], int]:
        similitudes: dict[tuple[str, str], int] = {}
        for nit, c in por_nit.items():
            base = nit[:-1]
            if not base or base == nit:
                continue
            otro = por_nit.get(base)
            if not otro:
                continue
            score = self._fuzz.similarity(
                normalize_company_name(otro["name"]), normalize_company_name(c["name"])
            )
            if score >= self._threshold:
                par = tuple(sorted([nit, base]))
                motivos[par].add(REASON_NIT_SUFFIX)
                similitudes[par] = score
        return similitudes
