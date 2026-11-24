"""E-04: Excel de configuración (bloqueos y ya subidas)."""
import openpyxl
import pytest

from src.odooInjection.domain.entities.injection_settings import InjectionSettings, valores_del_etl
from src.odooInjection.infrastructure.persistence.xlsx_injection_settings_source import (
    XlsxInjectionSettingsSource,
)


def test_configuracion_se_crea_y_se_lee_igual(tmp_path):
    ruta = tmp_path / "configuracion_inyeccion.xlsx"
    fuente = XlsxInjectionSettingsSource()
    assert not fuente.exists(ruta)
    fuente.create(ruta, valores_del_etl())
    assert fuente.read(ruta) == valores_del_etl()


def test_configuracion_ya_subidas_con_id_numerico(tmp_path):
    ruta = tmp_path / "c.xlsx"
    XlsxInjectionSettingsSource().create(ruta, InjectionSettings(ya_subidas={"860002585": 726280}))
    wb = openpyxl.load_workbook(ruta)
    wb["NITS_BLOQUEADOS"].append([900111111.0, "numérico en Excel"])
    wb.save(ruta)
    s = XlsxInjectionSettingsSource().read(ruta)
    assert s.ya_subidas == {"860002585": 726280}
    assert s.nits_bloqueados == {"900111111": "numérico en Excel"}


def test_configuracion_sin_hoja_da_mensaje_claro(tmp_path):
    ruta = tmp_path / "c.xlsx"
    XlsxInjectionSettingsSource().create(ruta, InjectionSettings())
    wb = openpyxl.load_workbook(ruta)
    del wb["YA_SUBIDAS"]
    wb.save(ruta)
    with pytest.raises(ValueError, match="le falta la hoja 'YA_SUBIDAS'"):
        XlsxInjectionSettingsSource().read(ruta)
