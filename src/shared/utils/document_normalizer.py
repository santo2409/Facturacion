"""Clasificación y normalización de documentos (NIT / cédula) para la opción 5.

Divergencia deliberada de `normalize_nit()` (`text_normalizer.py`): esa función
trunca SIEMPRE a 9 dígitos porque la consumen `scrapping` y `odooInjection`,
donde Odoo solo opera con NIT de 9 dígitos. Este módulo, en cambio, distingue
NIT de cédula y conserva la cédula íntegra — ver specs/006 para el porqué.
"""

import re
from dataclasses import dataclass

NIT = "NIT"
CEDULA = "CEDULA"

# Pesos DIAN, alineados desde el dígito menos significativo (derecha) del
# número base de 9 dígitos.
_DIAN_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)

_DIGITS_RE = re.compile(r"\D")


@dataclass(frozen=True)
class DocumentResult:
    value: str
    kind: str
    original: str
    truncated: bool
    dv_valid: bool | None


def clean_digits(text) -> str:
    """Elimina cualquier carácter no numérico."""
    if not text:
        return ""
    return _DIGITS_RE.sub("", str(text))


def calculate_dian_dv(base: str) -> int:
    """Dígito de verificación DIAN para un NIT base de 9 dígitos."""
    total = sum(int(d) * _DIAN_WEIGHTS[i] for i, d in enumerate(reversed(base)))
    residue = total % 11
    return residue if residue in (0, 1) else 11 - residue


def classify_document(digits: str) -> str:
    """Clasifica un documento ya limpio (solo dígitos) como NIT o CEDULA.

    Regla DIAN acordada: 9 dígitos con prefijo 8/9 -> NIT; 10 dígitos con
    prefijo 8/9 -> NIT con DV adjunto; cualquier otro caso -> CEDULA. La
    longitud es parte del criterio: hay cédulas de 7 dígitos con prefijo 8/9
    (ej. "8125007") que la regla de solo-prefijo clasificaría mal.
    """
    if len(digits) in (9, 10) and digits[:1] in ("8", "9"):
        return NIT
    return CEDULA


def normalize_document(text) -> DocumentResult:
    """Limpia, clasifica y normaliza un documento según su tipo."""
    digits = clean_digits(text)
    kind = classify_document(digits)

    if kind == CEDULA:
        return DocumentResult(
            value=digits, kind=kind, original=digits, truncated=False, dv_valid=None
        )

    truncated = len(digits) == 10
    value = digits[:9]
    dv_valid = None
    if truncated:
        dv_valid = calculate_dian_dv(value) == int(digits[9])

    return DocumentResult(
        value=value, kind=kind, original=digits, truncated=truncated, dv_valid=dv_valid
    )
