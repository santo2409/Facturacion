"""Los mapas y constantes copiados deben ser idénticos a los de ETL-Avancys (Pipeline.py)."""
import ast
from pathlib import Path

import pytest

from src.odooInjection.domain.entities import etl_constants
from src.odooInjection.domain.entities.injection_settings import valores_del_etl

PIPELINE = Path("/home/santiagosoa/Desarrollo/ETL-Avancys/Pipeline.py")


def _literales_del_etl() -> dict:
    arbol = ast.parse(PIPELINE.read_text(encoding="utf-8"))
    valores = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
            try:
                valores[nodo.targets[0].id] = ast.literal_eval(nodo.value)
            except ValueError:
                pass
    return valores


@pytest.mark.skipif(not PIPELINE.exists(), reason="ETL-Avancys no está en esta máquina")
@pytest.mark.parametrize("nombre", [
    "CIUDAD_CUENTA", "CIUDAD_CUENTA_ID", "SEDE_CUENTA", "RAMA_PRIORIDAD", "UMBRAL_CIUDAD",
    "SEDES_EXTRAMURALES", "COLS_FIJAS", "COLUMNAS_REQUERIDAS", "COLUMNAS_OPCIONALES",
])
def test_constante_igual_a_pipeline(nombre):
    assert getattr(etl_constants, nombre) == _literales_del_etl()[nombre]


@pytest.mark.skipif(not PIPELINE.exists(), reason="ETL-Avancys no está en esta máquina")
def test_regex_de_examen_igual_a_pipeline():
    assert 'RX_CODIGO_EXAMEN = re.compile(r"' + etl_constants.RX_CODIGO_EXAMEN.pattern + '")' in PIPELINE.read_text()


@pytest.mark.skipif(not PIPELINE.exists(), reason="ETL-Avancys no está en esta máquina")
def test_valores_iniciales_de_configuracion_iguales_a_pipeline():
    etl = _literales_del_etl()
    v = valores_del_etl()
    assert v.nits_bloqueados == etl["NITS_BLOQUEADOS"]
    assert v.empresas_bloqueadas == etl["EMPRESAS_BLOQUEADAS"]
    assert v.ya_subidas == etl["YA_SUBIDAS"]
