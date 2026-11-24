"""Pruebas del menú principal: las opciones en desuso (antes 3, 4, 5 y 9) se
eliminaron y el menú se renumeró."""

import main
from rich.console import Console

EXPECTED_MENU = [
    ("1", "Web Scrapping"),
    ("2", "Facturadores"),
    ("3", "Asignar Tarifas"),
    ("4", "Generar Pre Facturas"),
    ("5", "Cargar Pre Facturas"),
    ("6", "Empresas Facturadas a Otro NIT"),
    ("0", "Salir"),
]


def test_menu_tiene_solo_las_opciones_vigentes_renumeradas():
    assert main.MENU_OPTIONS == EXPECTED_MENU


def test_menu_renderizado_no_muestra_opciones_eliminadas():
    recorder = Console(record=True, width=120)
    recorder.print(main.build_menu_table())
    text = recorder.export_text()

    for removed in ("Tratamiento Información", "Cargar Tarifas", "Registrar Empresas", "Generar Faltantes", "Detectar Empresas Duplicadas", "deprecated"):
        assert removed not in text
    for _, description in EXPECTED_MENU:
        assert description in text


def test_opciones_que_ya_no_existen_son_invalidas(monkeypatch):
    printed = []
    monkeypatch.setattr(main.console, "print", lambda msg, *a, **k: printed.append(str(msg)))

    for option in ("7", "8", "9", "10"):
        assert main.dispatch_option(option, logger=None) is True

    assert printed == ["[red]Opción inválida[/red]"] * 4


def test_cada_opcion_llama_a_su_controller(monkeypatch):
    llamadas = []
    monkeypatch.setattr(main.console, "print", lambda *a, **k: None)
    monkeypatch.setenv("DAY_INITIAL", "1")
    monkeypatch.setenv("DAY_FINAL", "31")
    monkeypatch.setattr(main, "execute_web_scrapping", lambda logger: llamadas.append("1"))
    monkeypatch.setattr(main, "import_billers", lambda logger: llamadas.append("2"))
    monkeypatch.setattr(main, "assign_rates", lambda logger, with_invoices: llamadas.append("3"))
    monkeypatch.setattr(main, "generate_pre_invoices", lambda logger: llamadas.append("4"))
    monkeypatch.setattr(main, "load_pre_invoices", lambda logger: llamadas.append("5"))
    monkeypatch.setattr(main, "import_billing_redirects", lambda logger: llamadas.append("6"))

    for option in ("1", "2", "3", "4", "5", "6"):
        main.dispatch_option(option, logger=None)

    assert llamadas == ["1", "2", "3", "4", "5", "6"]
