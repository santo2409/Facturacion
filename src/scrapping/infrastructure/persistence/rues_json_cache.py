import json
from pathlib import Path

from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.utils.text_normalizer import normalize_nit


def load_rues_cache(path: Path | str) -> dict[str, NitResult]:
    """{nit normalizado: NitResult} con las entradas de `data.json` cuya fuente es RUES.

    Odoo es la fuente de verdad y se consulta siempre en vivo: las entradas de
    Odoo, de la BD local o sin `source` (formato anterior) se ignoran. Solo los
    resultados de RUES, lentos y con riesgo de bloqueo, se reutilizan.
    Un archivo ausente o ilegible devuelve un diccionario vacío.
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return {}

    cache: dict[str, NitResult] = {}
    for entry in data if isinstance(data, list) else []:
        if not str(entry.get("source") or "").startswith("RUES"):
            continue
        key = normalize_nit(str(entry.get("nit", "")))
        if not key:
            continue
        cache[key] = NitResult(
            nit=entry.get("nit"),
            is_company=bool(entry.get("is_company", False)),
            name=entry.get("name"),
            checked_bases=entry.get("checked_bases", ""),
            source=entry["source"],
            nit_original=entry.get("nit_original"),
            name_original=entry.get("name_original"),
            conflict=entry.get("conflict", ""),
        )
    return cache
