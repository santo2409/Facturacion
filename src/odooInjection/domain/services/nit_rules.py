"""Reglas de NIT de ETL-Avancys (`Pipeline.py:866-868`, `1058`).

Distintas de `normalize_nit` a propósito: aquí no se corta a 9 dígitos y se exige
de 6 a 12 dígitos (evita emparejar `ref_num='1'`, "CLIENTES MOSTRADOR").
"""


def limpiar_nit(nit) -> str:
    return str(nit or "").replace("-", "").replace(".", "").strip()


def nit_valido(nit) -> bool:
    nit_limpio = limpiar_nit(nit)
    return nit_limpio.isdigit() and 6 <= len(nit_limpio) <= 12
