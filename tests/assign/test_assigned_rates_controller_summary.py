from io import StringIO
from pathlib import Path

from rich.console import Console

from src.assign.application.use_cases.assigned_rates import AssignRatesResult
from src.assign.infrastructure.console.assigned_rates_controller import render_summary


def _render(result) -> str:
    console = Console(file=StringIO(), width=160, record=True, color_system=None)
    console.print(render_summary(result))
    return console.export_text()


def _result(**overrides):
    base = {
        "counts": {
            "odoo": 120,
            "fase_01_paquete_propio_local": 3,
            "fase_02_paquete_c_2025": 0,
            "fase_03_cualquier_paquete": 2,
            "fase_04_cup_base_paquete_c": 0,
            "fase_05_cup_base_cualquier_paquete": 0,
            "fase_06_cualquier_ciudad": 1,
            "sin_resolver": 4,
        },
        "findings_dir": Path("logs/asignar_tarifas/2026-10-10_1430"),
        "odoo_available": True,
    }
    base.update(overrides)
    return AssignRatesResult(**base)


def test_summary_lists_counts_and_folder():
    text = _render(_result())

    assert "Tarifa Odoo (especial/base)" in text and "120" in text
    assert "Fase 1 — Paquete propio local" in text
    assert "Fase 6 — Cualquier paquete/ciudad" in text
    assert "Sin resolver" in text
    assert "logs/asignar_tarifas/2026-10-10_1430" in text
    assert "Odoo no disponible" not in text


def test_summary_says_no_findings_without_folder():
    text = _render(_result(findings_dir=None))

    assert "Sin hallazgos" in text


def test_summary_warns_when_odoo_unavailable():
    text = _render(_result(odoo_available=False))

    assert "Odoo no disponible" in text
