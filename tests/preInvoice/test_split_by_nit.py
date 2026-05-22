"""Tests para SplitByNit — separación del CONSOLIDADO.xlsx por NIT."""
import logging
from pathlib import Path

import openpyxl
import pytest

from src.preInvoice.application.use_cases.split_by_nit import SplitByNit, FIXED_COLUMNS
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from tests.fakes.fake_cup_repo import FakeCupRepo


@pytest.fixture
def logger():
    adapter = LoggerAdapter("test_split")
    adapter._logger.setLevel(logging.DEBUG)
    return adapter


CUPS_CATALOG = [
    {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
    {"id": 2, "code": "890301", "name": "PERFIL LIPÍDICO"},
]


@pytest.fixture
def cup_repo():
    return FakeCupRepo(CUPS_CATALOG)


@pytest.fixture
def consolidado(tmp_path):
    path = tmp_path / "CONSOLIDADO.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado"
    header = [
        "Base", "Ingreso N°", "Sede", "Ciudad", "FACTURADOR",
        "Especial / General", "PAQUETE", "NIT", "Empresa", "Empresa Misión",
        "Medio de Pago", "Fecha Ingreso", "Tipo Examen", "Cargo", "Paciente",
        "N° Identificación", "Número de Póliza", "FACTURAS",
        "ORDEN, CENTRO DE COSTO, CECO, PET",
        "ORDEN, CENTRO DE COSTO, CECO, PET_1",
        "TIPO DE ACTIVIDAD", "Observaciones Ingreso", "Total",
        "890201", "890301",
    ]
    ws.append(header)
    ws.append(["B1", "I001", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-01",
               "Tipo1", "Cargo1", "Pac1", "1001", "Pol1", "SET001", "ORD1", "ORD1_1",
               "INTRA", "Obs1", 7000, 5000, 2000])
    ws.append(["B1", "I002", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-02",
               "Tipo1", "Cargo1", "Pac2", "1002", "Pol2", "SET002", "ORD2", "ORD2_1",
               "INTRA", "Obs2", 4000, 3000, 1000])
    ws.append(["B2", "I003", "S2", "MEDELLIN", "GENERAL", "Especial", "P2",
               "900222222", "EMPRESA B", "M2", "Tarjeta", "2026-01-03",
               "Tipo2", "Cargo2", "Pac3", "1003", "Pol3", "SET003", "ORD3", "ORD3_1",
               "EXTRA", "Obs3", 4000, 4000, None])
    wb.save(path)
    return path, tmp_path


def test_genera_subcarpetas_por_facturador(consolidado, logger, cup_repo):
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)
    # ALFA and GENERAL directories
    dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    dir_names = [d.name for d in dirs]
    assert "ALFA" in dir_names


def test_genera_libro_consolidado(consolidado, logger, cup_repo):
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)
    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    assert consolidado_path.exists()


def test_nit_con_multiples_filas_agrupa(consolidado, logger, cup_repo):
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)
    # NIT 900111111 has 2 rows
    archivo = next((output_dir / "ALFA").glob("*900111111*"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    ws = wb.active
    filas = sum(1 for _ in ws.iter_rows(min_row=3, values_only=True))
    wb.close()
    assert filas == 2


def test_fila_nombres_cups_en_fila_1(consolidado, logger, cup_repo):
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)
    archivo = next((output_dir / "ALFA").glob("*900111111*"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    ws = wb.active
    fila1 = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    wb.close()
    assert "HEMOGRAMA" in fila1


def test_general_con_factura_va_a_carpeta_general(consolidado, logger, cup_repo):
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)
    # NIT 900222222 has FACTURADOR=GENERAL and FACTURAS=SET003 → goes to "GENERAL" folder
    assert (output_dir / "GENERAL").exists()
