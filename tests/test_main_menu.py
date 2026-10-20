"""Tests del menú principal con etiqueta de desuso (spec 019, AC-04/AC-05)."""

import main
from rich.console import Console

from src.shared.utils.deprecated import DEPRECATED_LABEL, deprecated, is_deprecated


def test_menu_label_appends_label_only_when_deprecated():
    @deprecated()
    def old():
        pass

    def current():
        pass

    assert main.menu_label("Opción", old) == f"Opción {DEPRECATED_LABEL}"
    assert main.menu_label("Opción", current) == "Opción"
    assert main.menu_label("Salir", None) == "Salir"


def test_option_controllers_3_4_5_are_deprecated():
    options = {option: func for option, _, func in main.MENU_OPTIONS}

    for option in ("3", "4", "5"):
        assert is_deprecated(options[option]), f"opción {option} sin @deprecated"
    for option in ("1", "2", "6", "7", "9", "10"):
        assert not is_deprecated(options[option]), f"opción {option} deprecada"


def test_rendered_menu_marks_only_options_3_4_5():
    recorder = Console(record=True, width=120)
    recorder.print(main.build_menu_table())
    lines = recorder.export_text().splitlines()

    marked = {
        line.split()[0] for line in lines if line.strip() and "Desuso" in line
    }

    assert marked == {"3", "4", "5"}
