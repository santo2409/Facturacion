"""T15, T20: reglas puras de NIT y de ciudad (Pipeline.py:330-510, 866-868)."""
from src.odooInjection.domain.services.city_key import (
    clave_ciudad,
    clave_en_indice,
    cuenta_por_ciudad,
    elegir_rama,
    familia_de,
    trozos,
)
from src.odooInjection.domain.services.nit_rules import limpiar_nit, nit_valido


def test_t15_nit_valido_de_6_a_12_digitos_sin_puntos_ni_guion():
    assert nit_valido("900.111.111-1")
    assert nit_valido("123456")
    assert not nit_valido("12345")          # evita ref_num='1' (CLIENTES MOSTRADOR)
    assert not nit_valido("1234567890123")
    assert not nit_valido("NIT 900111111")
    assert not nit_valido(None)
    assert limpiar_nit(" 900.111.111-1 ") == "9001111111"


def test_t20_clave_de_ciudad_sin_tildes_puntuacion_ni_espacios():
    assert clave_ciudad("Bogotá, D.C.") == "BOGOTADC"
    assert clave_ciudad(None) == ""


def test_t20_trozos_por_palabra_completa():
    assert trozos("Guadalajara de Buga") == {"GUADALAJARADEBUGA", "DEBUGA", "BUGA", "GUADALAJARA", "GUADALAJARADE"}


def test_t19_ciudad_por_mapa_por_id_por_palabra_y_fuera_del_mapa():
    assert cuenta_por_ciudad("Bogota D.C.")[:3] == ("AA8638", None, "EXACTA")
    assert cuenta_por_ciudad("MARIQUITA")[:3] == (None, 11136, "ID")
    assert cuenta_por_ciudad("GUADALAJARA DE BUGA")[:3] == ("AA10460", None, "PALABRA")
    codigo, cid, como, motivo = cuenta_por_ciudad("PUEBLO INVENTADO")
    assert (codigo, cid, como) == (None, None, None) and "no esta en el mapa" in motivo
    assert cuenta_por_ciudad("")[3] == "La fila no trae ciudad"


def test_t21_familia_por_el_nombre_de_la_cuenta():
    assert familia_de("SEDE SOA - PROVEEDORES - TABIO") == "PROVEEDOR"
    assert familia_de("X - INTRAMURAL - SEDE 103 - BOGOTA D.C.") == "INTRAMURAL"
    assert familia_de("X - EXTRAMURAL - EXTRAMURAL - CALI") == "EXTRAMURAL"
    assert familia_de("OTRA COSA") == "OTRA"


def test_t21_rama_generica_y_ramas_de_cliente():
    generica = {"id": 1, "name": "SEDE SOA - PROVEEDORES - CALI"}
    cliente = {"id": 2, "name": "GRUPO ENEL - PROVEEDORES - CALI"}
    assert elegir_rama([generica, cliente]) == (generica, None)
    cuenta, motivo = elegir_rama([cliente, {"id": 3, "name": "CLIENTE NACIONAL - PROVEEDORES - CALI"}])
    assert cuenta is None and "ninguna generica" in motivo


def test_t20_clave_en_indice_exacta_palabra_y_parecido():
    indice = {("CALI", "PROVEEDOR"): [], ("BUGA", "PROVEEDOR"): [], ("MEDELLIN", "PROVEEDOR"): [],
              ("SANTAROSADEVITERBO", "PROVEEDOR"): []}
    assert clave_en_indice(indice, "Cali") == ("CALI", "EXACTA")
    assert clave_en_indice(indice, "GUADALAJARA DE BUGA") == ("BUGA", "PALABRA")
    assert clave_en_indice(indice, "SANTA ROSA DE VITERB")[0] == "SANTAROSADEVITERBO"
    assert clave_en_indice(indice, "MEDELIN") == (None, None)   # 93 < 95: no se acepta
    assert clave_en_indice(indice, "ZZZ") == (None, None)
