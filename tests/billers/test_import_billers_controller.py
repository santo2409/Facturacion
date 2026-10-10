"""Cableado del controller de la opción 2 (spec 011, RF-05 y RF-10)."""
from pathlib import Path

import openpyxl

import src.billers.infrastructure.console.import_billers_controller as controller
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from tests.fakes.fake_logger import FakeLogger


def test_use_case_receives_the_injected_logger():
    logger = FakeLogger()

    use_case = controller._build_use_case(object(), logger)

    assert use_case.logger is logger


def test_build_use_case_wires_findings_writer_for_facturadores():
    use_case = controller._build_use_case(object(), FakeLogger())

    assert isinstance(use_case.findings_writer, XlsxFindingsWriter)
    assert use_case.findings_writer._base_dir == Path("logs/facturadores")


def test_import_billers_executes_use_case_with_the_selected_sheet(monkeypatch, tmp_path):
    path = tmp_path / "facturadores.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Hoja1"
    wb.active.append(["NIT", "GESTOR", "EMPRESA"])
    wb.active.append(["900111111", "ALFA", "EMPRESA A"])
    wb.save(path)

    class _UseCase:
        executed_with = None

        def execute(self, df):
            _UseCase.executed_with = df

    built = {}

    def _fake_build(session, logger):
        built.update(session=session, logger=logger)
        return _UseCase()

    monkeypatch.setattr(controller, "ask_excel_path", lambda: path)
    monkeypatch.setattr(controller, "ask_sheet_name", lambda names: "Hoja1")
    monkeypatch.setattr(controller, "get_session", lambda: "sesion")
    monkeypatch.setattr(controller, "_build_use_case", _fake_build)
    logger = FakeLogger()

    controller.import_billers(logger)

    assert _UseCase.executed_with["NIT"].to_list() == ["900111111"]
    assert built["session"] == "sesion" and built["logger"] is logger


def test_build_use_case_injects_rues_cache_loader():
    """spec 016: data.json solo aporta resultados de RUES; Odoo se consulta siempre."""
    from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache

    use_case = controller._build_use_case(object(), FakeLogger())

    assert use_case.rues_cache_loader is load_rues_cache
