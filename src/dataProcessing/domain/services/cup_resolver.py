"""Servicio de dominio puro: cascada de 4 fases para corregir un CUP inválido.

F1 nombre exacto -> F2 co-ocurrencia inequívoca en la hoja -> F3 homologación
de sufijo -> F4 sugerencia difusa (nunca se aplica, solo se reporta).

Sin dependencias de Polars ni SQLAlchemy: se testea con fakes manuales.
Ver specs/005_correccion-cups-por-nombre/plan.md sección 3.3.
"""
from dataclasses import dataclass

from src.dataProcessing.domain.entities.cup_novelty import (
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_HOMOLOGADO_BASE,
    ESTADO_NO_CORREGIDO,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
    FASE_COOCURRENCIA,
    FASE_NOMBRE,
    FASE_SUFIJO,
    FASE_SUGERENCIA,
)
from src.shared.utils.text_normalizer import normalize_text_key


@dataclass(frozen=True)
class CupResolution:
    """Resultado de intentar resolver un CUP inválido."""

    cup: str
    corregido: bool
    estado: str | None = None
    fase: str | None = None
    detalle: str = ""


class CupResolver:
    def __init__(self, catalog: list[dict], fuzz=None, threshold: int = 90):
        self._codes = {c["code"].strip() for c in catalog}

        # Índice nombre normalizado -> código. Una clave colisionada (dos
        # nombres distintos que normalizan igual) se excluye por completo
        # (RF-08 / AC-04): no hay forma segura de decidir cuál es.
        by_name: dict[str, str] = {}
        collided: set[str] = set()
        for c in catalog:
            key = normalize_text_key(c["name"])
            if not key:
                continue
            if key in by_name and by_name[key] != c["code"]:
                collided.add(key)
            else:
                by_name[key] = c["code"]
        for key in collided:
            by_name.pop(key, None)
        self._by_name = by_name

        # Catálogo con clave normalizada, para pasarlo al fuzzy matcher.
        self._fuzz_catalog = [{"name": key} for key in by_name]
        self._name_by_key = {normalize_text_key(c["name"]): c["name"] for c in catalog}

        self._fuzz = fuzz
        self._threshold = threshold

    def is_valid(self, cup: str) -> bool:
        return (cup or "").strip() in self._codes

    def resolve(self, cup: str, examen: str | None, coocurrence: dict) -> CupResolution:
        cup = (cup or "").strip()

        if self.is_valid(cup):
            return CupResolution(cup=cup, corregido=False)

        key = normalize_text_key(examen) if examen else ""

        # F1: nombre exacto contra el catálogo
        if key and key in self._by_name:
            matched = self._by_name[key]
            return CupResolution(
                cup=matched,
                corregido=True,
                estado=ESTADO_CORREGIDO_NOMBRE,
                fase=FASE_NOMBRE,
                detalle=self._name_by_key.get(key, key),
            )

        # F2: co-ocurrencia inequívoca del mismo EXAMEN en la misma hoja
        if key and key in coocurrence:
            candidates = list(dict.fromkeys(coocurrence[key]))
            if len(candidates) == 1:
                return CupResolution(
                    cup=candidates[0],
                    corregido=True,
                    estado=ESTADO_CORREGIDO_COOCURRENCIA,
                    fase=FASE_COOCURRENCIA,
                    detalle=candidates[0],
                )
            if len(candidates) > 1:
                return CupResolution(
                    cup=cup,
                    corregido=False,
                    estado=ESTADO_NO_CORREGIDO,
                    fase=None,
                    detalle=f"CUPs en conflicto: {', '.join(candidates)}",
                )

        # F3: homologación de sufijo (904704-1 -> 904704)
        base_code = cup.split("-")[0]
        if base_code != cup and base_code in self._codes:
            return CupResolution(
                cup=base_code,
                corregido=True,
                estado=ESTADO_HOMOLOGADO_BASE,
                fase=FASE_SUFIJO,
                detalle=base_code,
            )

        # F4: sugerencia difusa. Nunca se aplica (RF-05 / AC-10): solo se
        # deja constancia en el reporte para revisión manual.
        if key and self._fuzz:
            suggested_key = self._fuzz.fuzz_property(key, self._fuzz_catalog, threshold=self._threshold)
            if suggested_key:
                suggested_code = self._by_name.get(suggested_key)
                if suggested_code:
                    return CupResolution(
                        cup=cup,
                        corregido=False,
                        estado=ESTADO_NO_CORREGIDO_SUGERENCIA,
                        fase=FASE_SUGERENCIA,
                        detalle=f"sugerencia: '{suggested_code}' {self._name_by_key.get(suggested_key, '')}".strip(),
                    )

        return CupResolution(cup=cup, corregido=False, estado=ESTADO_NO_CORREGIDO)
