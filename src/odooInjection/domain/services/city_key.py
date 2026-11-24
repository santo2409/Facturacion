"""Normalización de ciudades y emparejamiento contra el mapa y el índice de cuentas.

Copia de ETL-Avancys `Pipeline.py` (7bb6784): `_normalizar` (330), `_clave_ciudad` (335),
`familia_de` (374), `_clave_en_indice` (410), `_elegir_rama` (433), `_trozos` (452) y
`cuenta_por_ciudad` (468). Funciones puras: sin Odoo ni E/S.
"""

import re
import unicodedata

from rapidfuzz import fuzz, process

from src.odooInjection.domain.entities.etl_constants import (
    CIUDAD_CUENTA,
    CIUDAD_CUENTA_ID,
    FAMILIA_EXTRAMURAL,
    FAMILIA_INTRAMURAL,
    FAMILIA_PROVEEDOR,
    RAMA_PRIORIDAD,
    SEDE_CUENTA,
    UMBRAL_CIUDAD,
)


def normalizar(s):
    s = s.upper().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clave_ciudad(s):
    """Sin tildes, sin puntuación y sin espacios: 'BOGOTA, D.C.' y 'BOGOTA D.C.' son la misma clave."""
    return re.sub(r"[^A-Z0-9]", "", normalizar(str(s or "")))


CIUDAD_CUENTA_CLAVE = {clave_ciudad(k): v for k, v in CIUDAD_CUENTA.items()}
CIUDAD_ID_CLAVE = {clave_ciudad(k): v for k, v in CIUDAD_CUENTA_ID.items()}
SEDE_CUENTA_CLAVE = {clave_ciudad(k): v for k, v in SEDE_CUENTA.items()}


def familia_de(nombre):
    n = (nombre or "").upper()
    if "PROVEEDORES" in n:
        return FAMILIA_PROVEEDOR
    if FAMILIA_INTRAMURAL in n:
        return FAMILIA_INTRAMURAL
    if FAMILIA_EXTRAMURAL in n:
        return FAMILIA_EXTRAMURAL
    return "OTRA"


def trozos(ciudad_raw):
    """La ciudad completa y sus prefijos y sufijos de palabras completas:
    'GUADALAJARA DE BUGA' da GUADALAJARADEBUGA, BUGA, DEBUGA, GUADALAJARA, GUADALAJARADE."""
    palabras = [p for p in re.split(r"[^A-Z0-9]+", normalizar(ciudad_raw)) if p]
    resultado = set()
    for i in range(len(palabras)):
        resultado.add("".join(palabras[i:]))      # sufijos
        resultado.add("".join(palabras[:i + 1]))  # prefijos
    return resultado


def clave_en_indice(indice, ciudad_raw):
    """Clave de ciudad para buscar en el índice: exacta, por palabra o por parecido.
    Devuelve (clave, como) o (None, motivo)."""
    clave = clave_ciudad(ciudad_raw)
    claves = {k for k, _f in indice}
    if clave in claves:
        return clave, "EXACTA"

    porpalabra = sorted(k for k in trozos(ciudad_raw) if k in claves)
    if len(porpalabra) == 1:
        return porpalabra[0], "PALABRA"

    mejores = process.extract(clave, sorted(claves), scorer=fuzz.WRatio, limit=2)
    if mejores and mejores[0][1] >= UMBRAL_CIUDAD:
        if len(mejores) == 1 or mejores[1][1] < UMBRAL_CIUDAD:
            return mejores[0][0], "PARECIDO " + str(round(mejores[0][1])) + "%"
        return None, ("Ciudad '" + str(ciudad_raw) + "' se parece por igual a " +
                      mejores[0][0] + " y " + mejores[1][0] + " — desempatar a mano")
    return None, None


def elegir_rama(cuentas):
    """De varias cuentas de la misma ciudad y familia, la de la rama más genérica.
    Devuelve (cuenta, None) o (None, motivo)."""
    if len(cuentas) == 1:
        return cuentas[0], None
    for rama in RAMA_PRIORIDAD:
        delarama = [c for c in cuentas if c["name"].upper().startswith(rama)]
        if len(delarama) == 1:
            return delarama[0], None
        if len(delarama) > 1:
            return None, ("Hay " + str(len(delarama)) + " cuentas de '" + rama +
                          "' para esa ciudad y familia: " +
                          ", ".join(str(c["id"]) + "=" +
                                    c["name"].split(" - ")[-2] for c in delarama))
    return None, ("Las " + str(len(cuentas)) + " cuentas candidatas son de ramas "
                  "de un cliente o area concreta, ninguna generica: " +
                  ", ".join(str(c["id"]) + "=" + c["name"].split(" - ")[0]
                            for c in cuentas))


def cuenta_por_ciudad(ciudad_raw):
    """Ciudad del archivo → (codigo, id, como, motivo). Sin respaldo a Bogotá:
    si no se resuelve, código e id son None y 'motivo' dice por qué."""
    clave = clave_ciudad(ciudad_raw)
    if not clave:
        return None, None, None, "La fila no trae ciudad"

    if clave in CIUDAD_ID_CLAVE:
        return None, CIUDAD_ID_CLAVE[clave], "ID", None
    if clave in CIUDAD_CUENTA_CLAVE:
        return CIUDAD_CUENTA_CLAVE[clave], None, "EXACTA", None

    candidatos_trozos = trozos(ciudad_raw)
    candidatos = sorted({k for k in candidatos_trozos if k in CIUDAD_CUENTA_CLAVE} |
                        {k for k in candidatos_trozos if k in CIUDAD_ID_CLAVE})
    if len(candidatos) == 1:
        k = candidatos[0]
        if k in CIUDAD_ID_CLAVE:
            return None, CIUDAD_ID_CLAVE[k], "PALABRA", None
        return CIUDAD_CUENTA_CLAVE[k], None, "PALABRA", None
    if len(candidatos) > 1:
        return None, None, None, ("Ciudad '" + str(ciudad_raw) +
                                  "' encaja con varias del mapa: " +
                                  ", ".join(candidatos) + " — desempatar a mano")

    # La sugerencia del fuzzy es SOLO una pista para el humano, nunca para imputar.
    pista = process.extractOne(clave, list(CIUDAD_CUENTA_CLAVE), scorer=fuzz.WRatio)
    sug = ("; lo mas parecido en el mapa es '" + pista[0] +
           "' (" + str(round(pista[1])) + "%) — confirmar, no asumir") if pista else ""
    return None, None, None, ("Ciudad '" + str(ciudad_raw) +
                              "' no esta en el mapa de cuentas analiticas" + sug)
