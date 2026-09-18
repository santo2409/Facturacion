"""Entidad de dominio para las novedades detectadas al corregir CUPs en la
opción 3 (Tratamiento Información). Ver specs/005_correccion-cups-por-nombre/.
"""
from dataclasses import dataclass, field

# Estados posibles de una novedad (RF-10)
ESTADO_CRUCE_CUP_VALOR = "CUP y VALOR cruzados"
ESTADO_CORREGIDO_NOMBRE = "CUP corregido por nombre"
ESTADO_CORREGIDO_COOCURRENCIA = "CUP corregido por co-ocurrencia"
ESTADO_HOMOLOGADO_BASE = "CUP homologado al CUP base"
ESTADO_NO_CORREGIDO_SUGERENCIA = "CUP no existe en el catálogo (sugerencia)"
ESTADO_NO_CORREGIDO = "CUP no existe en el catálogo"

# Fases de la cascada de resolución (RF-06)
FASE_SWAP = "F0"
FASE_NOMBRE = "F1"
FASE_COOCURRENCIA = "F2"
FASE_SUFIJO = "F3"
FASE_SUGERENCIA = "F4"


@dataclass
class CupNovelty:
    """Una novedad de CUP agrupada por (hoja, cup_original, examen, cup_corregido, estado)."""

    hoja: str
    cup_original: str
    examen: str
    cup_corregido: str | None
    detalle: str
    estado: str
    fase: str
    filas: int = 1
    contratos: list[str] = field(default_factory=list)
