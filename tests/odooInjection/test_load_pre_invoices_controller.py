"""Controller de la opción 5: configuración de Odoo y Excel de configuración."""
from src.odooInjection.infrastructure.console import load_pre_invoices_controller as ctrl
from src.odooInjection.infrastructure.persistence.xlsx_injection_settings_source import (
    XlsxInjectionSettingsSource,
)
from src.odooInjection.domain.entities.injection_settings import valores_del_etl
from tests.fakes.fake_logger import FakeLogger


def _entorno(monkeypatch, tmp_path, **extra):
    for k in ("ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_API_KEY", "INYECCION_CONFIG_XLSX", "INYECCION_SALIDA"):
        monkeypatch.delenv(k, raising=False)
    valores = {"ODOO_URL": "http://x.invalid", "ODOO_DB": "db", "ODOO_USERNAME": "u", "ODOO_API_KEY": "k",
               "INYECCION_CONFIG_XLSX": str(tmp_path / "configuracion_inyeccion.xlsx")}
    valores.update(extra)
    for k, v in valores.items():
        if v is not None:
            monkeypatch.setenv(k, v)


def test_controller_sin_variables_de_odoo_no_sigue(monkeypatch, tmp_path):
    _entorno(monkeypatch, tmp_path, ODOO_DB=None, ODOO_API_KEY=None)
    logger = FakeLogger()
    assert ctrl.load_pre_invoices(logger) is None
    assert any("ODOO_DB, ODOO_API_KEY" in e for e in logger.errors)


def test_controller_primera_vez_crea_la_configuracion_con_valores_del_etl(monkeypatch, tmp_path):
    _entorno(monkeypatch, tmp_path)
    monkeypatch.setattr(ctrl, "ask_folder_path", lambda *_: (_ for _ in ()).throw(AssertionError("no debe pedir carpeta")))
    assert ctrl.load_pre_invoices(FakeLogger()) is None
    assert XlsxInjectionSettingsSource().read(tmp_path / "configuracion_inyeccion.xlsx") == valores_del_etl()


def test_controller_con_configuracion_pide_carpeta_y_ejecuta(monkeypatch, tmp_path):
    _entorno(monkeypatch, tmp_path, INYECCION_SALIDA=str(tmp_path / "salida"))
    XlsxInjectionSettingsSource().create(tmp_path / "configuracion_inyeccion.xlsx", valores_del_etl())
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    monkeypatch.setattr(ctrl, "ask_folder_path", lambda *_: entrada)
    logger = FakeLogger()
    assert ctrl.load_pre_invoices(logger) is None        # carpeta vacía: no conecta a Odoo
    assert any("No se encontraron archivos" in e for e in logger.errors)
    assert not (tmp_path / "salida").exists()            # sin libros vacíos (ADR-014)
