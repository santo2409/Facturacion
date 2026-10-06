import openpyxl

from src.company.domain.entities.unlinked_row import UnlinkedRow
from src.company.infrastructure.reporting.not_linked_companies_log_generator import (
    NotLinkedCompaniesLogGenerator,
)
from tests.fakes.fake_logger import FakeLogger


def _rows(log_path):
    wb = openpyxl.load_workbook(log_path, data_only=True)
    ws = wb.active
    rows = [
        row for row in ws.iter_rows(min_row=2, values_only=True)
        if row and row[1] not in (None, "")
    ]
    wb.close()
    return rows


def test_genera_excel_con_filas_no_vinculadas(tmp_path):
    gen = NotLinkedCompaniesLogGenerator(FakeLogger())
    rows = [
        UnlinkedRow(
            document="900111111",
            company_name="EMPRESA A",
            package="PAQUETE BASICO",
            reason="Empresa no encontrada en la base de datos",
        )
    ]

    log_path = gen.generate(rows, tmp_path)

    assert log_path.name == "empresas_no_vinculadas.xlsx"
    assert log_path.exists()
    written = _rows(log_path)
    assert len(written) == 1
    row = written[0]
    assert row[1] == "900111111"
    assert row[2] == "EMPRESA A"
    assert row[3] == "PAQUETE BASICO"
    assert row[4] == "Empresa no encontrada en la base de datos"


def test_reporte_vacio_cuando_no_hay_filas(tmp_path):
    gen = NotLinkedCompaniesLogGenerator(FakeLogger())

    log_path = gen.generate([], tmp_path)

    assert log_path.exists()
    assert _rows(log_path) == []


def test_columnas_y_encabezados_correctos(tmp_path):
    gen = NotLinkedCompaniesLogGenerator(FakeLogger())
    log_path = gen.generate([], tmp_path)

    wb = openpyxl.load_workbook(log_path)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    wb.close()
    assert headers == ["#", "Documento", "Razón Social", "Paquete", "Motivo", "Fecha/Hora"]


def test_logger_recibe_resumen_con_conteo(tmp_path):
    logger = FakeLogger()
    gen = NotLinkedCompaniesLogGenerator(logger)
    rows = [
        UnlinkedRow("900111111", "EMPRESA A", "PAQUETE BASICO", "Empresa no encontrada"),
        UnlinkedRow("900222222", "EMPRESA B", "PAQUETE BASICO", "Empresa no encontrada"),
    ]

    gen.generate(rows, tmp_path)

    assert len(logger.infos) == 1
    assert "2" in logger.infos[0]
