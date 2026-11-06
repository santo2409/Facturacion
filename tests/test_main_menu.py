"""Tests del menú principal con etiqueta de desuso (spec 019, AC-04/AC-05)."""

import main
from rich.console import Console
from rich.text import Text

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


# Opciones en desuso: 3, 4 y 5 (spec 019) y 9 (a196be6; confirmado en P-01 de docs/auditoria.md).
DEPRECATED_OPTIONS = {"3", "4", "5", "9"}
ACTIVE_OPTIONS = {"1", "2", "6", "7", "10"}


def test_option_controllers_3_4_5_9_are_deprecated():
    options = {option: func for option, _, func in main.MENU_OPTIONS}

    for option in sorted(DEPRECATED_OPTIONS):
        assert is_deprecated(options[option]), f"opción {option} sin @deprecated"
    for option in sorted(ACTIVE_OPTIONS):
        assert not is_deprecated(options[option]), f"opción {option} deprecada"


def test_rendered_menu_marks_only_options_3_4_5_9():
    recorder = Console(record=True, width=120)
    recorder.print(main.build_menu_table())
    lines = recorder.export_text().splitlines()
    # Texto visible de la etiqueta, sin markup (af5f906 la cambió de "Desuso" a "**deprecated**").
    label_text = Text.from_markup(DEPRECATED_LABEL).plain

    marked = {
        line.split()[0] for line in lines if line.strip() and label_text in line
    }

    assert marked == DEPRECATED_OPTIONS
