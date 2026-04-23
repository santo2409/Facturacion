"""Tests para SplitByNit — separación del CONSOLIDADO.xlsx por NIT."""
import logging
from pathlib import Path

import openpyxl
import pytest

from src.preInvoice.application.use_cases.split_by_nit import SplitByNit
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


@pytest.fixture
def logger():
    adapter = LoggerAdapter("test_split")
    adapter._logger.setLevel(logging.DEBUG)
    return adapter


@pytest.fixture
def consolidado(tmp_path):
    """Genera un CONSOLIDADO.xlsx temporal con 3 NITs y columna Total."""
    path = tmp_path / "CONSOLIDADO.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado"

    header = ["NIT", "Empresa", "Ciudad", "FACTURADOR", "890201", "890301", "Total"]
    ws.append(header)
    ws.append(["900111111", "EMPRESA A", "BOGOTA", "ALFA", 5000, 2000, 7000])
    ws.append(["900111111", "EMPRESA A", "BOGOTA", "ALFA", 3000, 1000, 4000])
    ws.append(["900222222", "EMPRESA B", "MEDELLIN", "BETA", 4000, 3000, 7000])
    ws.append(["900333333", "EMPRESA C", "CALI", "GENERAL", 1000, 500, 1500])

    wb.save(path)
    return path, tmp_path


def test_genera_archivos_por_nit(consolidado, logger):
    """3 NITs distintos → genera 3 archivos en NITs/."""
    path, output_dir = consolidado
    SplitByNit(logger).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    assert nits_dir.exists()
    archivos = list(nits_dir.glob("*.xlsx"))
    assert len(archivos) == 3


def test_suma_filas_igual_al_consolidado(consolidado, logger):
    """La suma de filas de archivos separados == filas del consolidado."""
    path, output_dir = consolidado
    SplitByNit(logger).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    total_filas = 0
    for archivo in nits_dir.glob("*.xlsx"):
        wb = openpyxl.load_workbook(archivo, read_only=True)
        ws = wb.active
        filas = sum(1 for _ in ws.iter_rows(min_row=2, values_only=True))
        total_filas += filas
        wb.close()

    # El consolidado tiene 4 filas de datos
    assert total_filas == 4


def test_genera_libro_consolidado_con_hojas(consolidado, logger):
    """Genera NITs_consolidado.xlsx con una hoja por NIT."""
    path, output_dir = consolidado
    SplitByNit(logger).execute(path, output_dir)

    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    assert consolidado_path.exists()

    wb = openpyxl.load_workbook(consolidado_path, read_only=True)
    assert len(wb.sheetnames) == 3
    wb.close()


def test_nit_con_multiples_filas_agrupa_correctamente(consolidado, logger):
    """NIT 900111111 tiene 2 filas → su archivo debe tener 2 filas."""
    path, output_dir = consolidado
    SplitByNit(logger).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    # Buscar el archivo de EMPRESA A
    archivo_a = next(
        (f for f in nits_dir.glob("*.xlsx") if "EMPRESA A" in f.name), None
    )
    assert archivo_a is not None

    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    filas = sum(1 for _ in ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    assert filas == 2
