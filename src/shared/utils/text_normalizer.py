import re

import polars as pl
from unidecode import unidecode

_CLEAN_RE = re.compile(r"[^A-Z&Ñ0-9\s]")
_CLEAN_HASH_RE = re.compile(r"[^A-Z&Ñ#0-9\s]")
_SPACES_RE = re.compile(r"\s+")


def normalize_name(text: str) -> str:
    """Uppercase, remove special chars (keep &Ñ), collapse spaces, strip."""
    if not text:
        return ""
    s = _CLEAN_RE.sub("", text.upper())
    return _SPACES_RE.sub(" ", s).strip()


def normalize_name_hash(text: str) -> str:
    """Like normalize_name but also keeps #."""
    if not text:
        return ""
    s = _CLEAN_HASH_RE.sub("", text.upper())
    return _SPACES_RE.sub(" ", s).strip()


def normalize_upper_spaces(text: str) -> str:
    """Uppercase, collapse spaces, strip."""
    if not text:
        return ""
    return _SPACES_RE.sub(" ", text.strip().upper())


def normalize_text_key(text: str) -> str:
    """Clave canónica para comparar nombres (razones sociales, exámenes, etc.).

    Translitera los acentos antes de limpiar porque `normalize_name` elimina
    las letras acentuadas en vez de convertirlas ("CLÍNICA" -> "CLNICA").
    """
    return normalize_name(unidecode(text or ""))


def normalize_company_name(text: str) -> str:
    """Normaliza una razón social para compararla. Alias de `normalize_text_key`."""
    return normalize_text_key(text)


def normalize_nit(text: str) -> str:
    """Extract digits, take first 9."""
    if not text:
        return ""
    digits = re.sub(r"\D", "", str(text))
    return digits[:9]


def pl_normalize_name(col: str) -> pl.Expr:
    """Polars expression: uppercase + remove special chars + collapse spaces."""
    return (
        pl.col(col)
        .str.to_uppercase()
        .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
    )


def pl_normalize_upper(col: str) -> pl.Expr:
    """Polars expression: strip + uppercase + collapse spaces."""
    return (
        pl.col(col)
        .str.strip_chars()
        .str.to_uppercase()
        .str.replace_all(r"\s+", " ")
    )
