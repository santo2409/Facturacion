"""Pruebas de RedirectedCompaniesLogGenerator (logs/empresas_redirigidas.xlsx)."""
import openpyxl

from src.company.domain.entities.redirect_assignment import RedirectAssignment
from src.company.infrastructure.reporting.redirected_companies_log_generator import (
    RedirectedCompaniesLogGenerator,
)
from tests.fakes.fake_logger import FakeLogger


def test_redirigidas_escribe_una_fila_por_empresa_y_totales(tmp_path):
    filas = [
        RedirectAssignment("OTRA", "800000001", "A", "901555555", "A(OTRA)", 3),
        RedirectAssignment("NORTE", "800000002", "B", "902666666", "B(NORTE)", 2),
    ]

    log_path = RedirectedCompaniesLogGenerator(FakeLogger()).generate(filas, tmp_path)

    assert log_path.name == "empresas_redirigidas.xlsx"
    wb = openpyxl.load_workbook(log_path, data_only=True)
    ws = wb.active
    assert ws.title == "Empresas Redirigidas"
    datos = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[1]]
    assert datos == [
        (1, "OTRA", "800000001", "A", "901555555", "A(OTRA)", 3),
        (2, "NORTE", "800000002", "B", "902666666", "B(NORTE)", 2),
    ]
    totales = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[3] == "TOTAL"]
    assert totales == [(None, None, None, "TOTAL", None, 2, 5)]
    wb.close()
