"""Cableado del controller de la opción 4 (spec 011, RF-04)."""
from pathlib import Path

import openpyxl

import src.rates.infrastructure.console.import_rates_controller as controller
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from tests.fakes.fake_logger import FakeLogger


def test_build_use_case_wires_findings_writer_for_cargar_tarifas():
    use_case = controller._build_use_case(object(), FakeLogger(), ExcelLoader())

    assert isinstance(use_case.findings_writer, XlsxFindingsWriter)
    assert use_case.findings_writer._base_dir == Path("logs/cargar_tarifas")


def test_import_rates_executes_use_case_with_the_loaded_excel(monkeypatch, tmp_path):
    path = tmp_path / "tarifas.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["CONTRATO"])
    wb.save(path)

    class _UseCase:
        executed_with = None

        def execute(self, excel):
            _UseCase.executed_with = excel

    built = {}

    def _fake_build(session, logger, loader):
        built.update(session=session, logger=logger, loader=loader)
        return _UseCase()

    monkeypatch.setattr(controller, "ask_excel_path", lambda: path)
    monkeypatch.setattr(controller, "get_session", lambda: "sesion")
    monkeypatch.setattr(controller, "_build_use_case", _fake_build)
    logger = FakeLogger()

    controller.import_rates(logger)

    assert _UseCase.executed_with.path == path
    assert built["session"] == "sesion" and built["logger"] is logger
