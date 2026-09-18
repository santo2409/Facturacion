"""Tests para la entidad CupNovelty y sus constantes de estado/fase."""
from src.dataProcessing.domain.entities.cup_novelty import (
    CupNovelty,
    ESTADO_CRUCE_CUP_VALOR,
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_HOMOLOGADO_BASE,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
    ESTADO_NO_CORREGIDO,
    FASE_SWAP,
    FASE_NOMBRE,
    FASE_COOCURRENCIA,
    FASE_SUFIJO,
    FASE_SUGERENCIA,
)


def test_cup_novelty_defaults_and_fields():
    novelty = CupNovelty(
        hoja="Paquetes",
        cup_original="10042",
        examen="PROTECCION AUDITIVA",
        cup_corregido="100042",
        detalle="PROTECCION AUDITIVA",
        estado=ESTADO_CORREGIDO_NOMBRE,
        fase=FASE_NOMBRE,
    )

    assert novelty.hoja == "Paquetes"
    assert novelty.cup_original == "10042"
    assert novelty.cup_corregido == "100042"
    assert novelty.estado == ESTADO_CORREGIDO_NOMBRE
    assert novelty.fase == FASE_NOMBRE
    # defaults
    assert novelty.filas == 1
    assert novelty.contratos == []


def test_cup_novelty_estado_constants_are_distinct_strings():
    estados = {
        ESTADO_CRUCE_CUP_VALOR,
        ESTADO_CORREGIDO_NOMBRE,
        ESTADO_CORREGIDO_COOCURRENCIA,
        ESTADO_HOMOLOGADO_BASE,
        ESTADO_NO_CORREGIDO_SUGERENCIA,
        ESTADO_NO_CORREGIDO,
    }
    assert len(estados) == 6
    assert all(isinstance(e, str) and e for e in estados)


def test_cup_novelty_fase_constants_are_distinct_strings():
    fases = {FASE_SWAP, FASE_NOMBRE, FASE_COOCURRENCIA, FASE_SUFIJO, FASE_SUGERENCIA}
    assert len(fases) == 5


def test_cup_novelty_contratos_default_is_independent_per_instance():
    a = CupNovelty(
        hoja="Paquetes", cup_original="1", examen="E", cup_corregido=None,
        detalle="", estado=ESTADO_NO_CORREGIDO, fase=FASE_SUGERENCIA,
    )
    b = CupNovelty(
        hoja="Paquetes", cup_original="2", examen="E", cup_corregido=None,
        detalle="", estado=ESTADO_NO_CORREGIDO, fase=FASE_SUGERENCIA,
    )
    a.contratos.append("X")
    assert b.contratos == []
