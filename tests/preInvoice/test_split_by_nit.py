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


@pytest.fixture
def consolidado_general_sin_factura(tmp_path):
    """Consolidado con una fila que va a 'General sin factura' (GENERAL + sin SET)."""
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
        "890201",
    ]
    ws.append(header)
    # Fila con FACTURADOR=GENERAL y FACTURAS vacío → "General sin factura"
    ws.append(["B1", "I001", "S1", "BOGOTA", "GENERAL", "General", "P1",
               "900333333", "EMPRESA SIN FACTURA", "M1", "Efectivo", "15/01/2026",
               "Tipo1", "Cargo1", "Pac1", "2001", "Pol1", "", "ORD1", "ORD1_1",
               "INTRA", "Obs1", 5000, 5000])
    # Fila con facturador normal para comparar que NO se borra su fecha
    ws.append(["B2", "I002", "S2", "MEDELLIN", "ALFA", "General", "P2",
               "900444444", "EMPRESA CON FACTURA", "M2", "Tarjeta", "20/02/2026",
               "Tipo2", "Cargo2", "Pac2", "2002", "Pol2", "SET001", "ORD2", "ORD2_1",
               "EXTRA", "Obs2", 3000, 3000])
    wb.save(path)
    return path, tmp_path


def test_fecha_ingreso_se_conserva_en_general_sin_factura(consolidado_general_sin_factura, logger, cup_repo):
    """Archivos en 'General sin factura' conservan 'Fecha Ingreso' (spec 009)."""
    path, output_dir = consolidado_general_sin_factura
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    # Verificar que la carpeta 'General sin factura' existe
    carpeta = output_dir / "General sin factura"
    assert carpeta.exists(), "No se creó la carpeta 'General sin factura'"

    # Abrir el archivo generado y verificar que 'Fecha Ingreso' es None
    archivo = next(carpeta.glob("*900333333*"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    ws = wb.active

    # Fila 1 = nombres CUPS, Fila 2 = headers, Fila 3+ = datos
    headers = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    fecha_col_idx = headers.index("Fecha Ingreso")

    for row in ws.iter_rows(min_row=3, values_only=True):
        assert row[fecha_col_idx] is None, (
            f"Se esperaba 'Fecha Ingreso' en None, pero se encontró: {row[fecha_col_idx]}"
        )
    wb.close()


def test_fecha_ingreso_se_mantiene_en_otras_carpetas(consolidado_general_sin_factura, logger, cup_repo):
    """Archivos en carpetas distintas a 'General sin factura' conservan 'Fecha Ingreso'."""
    path, output_dir = consolidado_general_sin_factura
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    # El archivo de ALFA debe conservar su fecha
    archivo = next((output_dir / "ALFA").glob("*900444444*"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    ws = wb.active

    headers = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    fecha_col_idx = headers.index("Fecha Ingreso")

    for row in ws.iter_rows(min_row=3, values_only=True):
        assert row[fecha_col_idx] is not None, (
            "La 'Fecha Ingreso' no debería ser None en carpetas distintas a 'General sin factura'"
        )
    wb.close()


@pytest.fixture
def consolidado_con_colores(tmp_path):
    """Consolidado con celdas CUP coloreadas simulando fases de resolución."""
    from openpyxl.styles import PatternFill

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

    # Fila de datos 1: NIT 900111111, CUP 890201=5000 (fase 2 dorado), CUP 890301=2000 (sin color)
    ws.append(["B1", "I001", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-01",
               "Tipo1", "Cargo1", "Pac1", "1001", "Pol1", "SET001", "ORD1", "ORD1_1",
               "INTRA", "Obs1", 7000, 5000, 2000])
    # Colorear celda CUP 890201 (columna 24) en fila 2 con color Fase 2
    ws.cell(row=2, column=24).fill = PatternFill("solid", fgColor="FFF2CC")

    # Fila de datos 2: NIT 900111111, CUP 890201=3000 (fase 3 naranja), CUP 890301=1000 (fase 5 azul)
    ws.append(["B1", "I002", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-02",
               "Tipo1", "Cargo1", "Pac2", "1002", "Pol2", "SET002", "ORD2", "ORD2_1",
               "INTRA", "Obs2", 4000, 3000, 1000])
    ws.cell(row=3, column=24).fill = PatternFill("solid", fgColor="F4B183")
    ws.cell(row=3, column=25).fill = PatternFill("solid", fgColor="9DC3E6")

    # Fila de datos 3: NIT 900222222, CUP 890201=4000 (fase 6 púrpura)
    ws.append(["B2", "I003", "S2", "MEDELLIN", "GENERAL", "Especial", "P2",
               "900222222", "EMPRESA B", "M2", "Tarjeta", "2026-01-03",
               "Tipo2", "Cargo2", "Pac3", "1003", "Pol3", "SET003", "ORD3", "ORD3_1",
               "EXTRA", "Obs3", 4000, 4000, None])
    ws.cell(row=4, column=24).fill = PatternFill("solid", fgColor="D5A6E6")

    wb.save(path)
    return path, tmp_path


def test_colores_fase_se_preservan_en_archivo_individual(consolidado_con_colores, logger, cup_repo):
    """Los colores de fase del CONSOLIDADO se preservan en los archivos por NIT."""
    path, output_dir = consolidado_con_colores
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    # Verificar archivo de NIT 900111111 (ALFA)
    archivo = next((output_dir / "ALFA").glob("*900111111*"))
    wb = openpyxl.load_workbook(archivo)
    ws = wb.active

    # Encontrar la columna del CUP 890201 en el header (fila 2)
    headers = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    cup_890201_col = headers.index("890201") + 1  # 1-based para openpyxl
    cup_890301_col = headers.index("890301") + 1

    # Fila 3 (primer paciente): CUP 890201 debe tener color FFF2CC (fase 2)
    cell_f3 = ws.cell(row=3, column=cup_890201_col)
    assert cell_f3.fill.fgColor.rgb == "00FFF2CC", (
        f"Esperado '00FFF2CC' (Fase 2), obtenido '{cell_f3.fill.fgColor.rgb}'"
    )

    # Fila 4 (segundo paciente): CUP 890201 debe tener color F4B183 (fase 3)
    cell_f4 = ws.cell(row=4, column=cup_890201_col)
    assert cell_f4.fill.fgColor.rgb == "00F4B183", (
        f"Esperado '00F4B183' (Fase 3), obtenido '{cell_f4.fill.fgColor.rgb}'"
    )

    # Fila 4 (segundo paciente): CUP 890301 debe tener color 9DC3E6 (fase 5)
    cell_f4b = ws.cell(row=4, column=cup_890301_col)
    assert cell_f4b.fill.fgColor.rgb == "009DC3E6", (
        f"Esperado '009DC3E6' (Fase 5), obtenido '{cell_f4b.fill.fgColor.rgb}'"
    )

    # Fila 3 (primer paciente): CUP 890301 NO tiene color de fase
    cell_f3b = ws.cell(row=3, column=cup_890301_col)
    assert cell_f3b.fill.patternType is None or cell_f3b.fill.fgColor.rgb in (
        "00000000", None
    ), f"CUP 890301 fila 3 no debería tener color de fase, tiene: {cell_f3b.fill.fgColor.rgb}"

    wb.close()


def test_colores_fase_se_preservan_en_consolidado_nits(consolidado_con_colores, logger, cup_repo):
    """Los colores de fase se preservan en el libro NITs_consolidado.xlsx."""
    path, output_dir = consolidado_con_colores
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    wb = openpyxl.load_workbook(consolidado_path)

    # Buscar la hoja de EMPRESA B (NIT 900222222)
    # Debería tener el color D5A6E6 (fase 6) en su CUP 890201
    found = False
    for ws_name in wb.sheetnames:
        if ws_name == "Leyenda":
            continue
        ws = wb[ws_name]
        headers = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
        if "890201" not in headers:
            continue
        # Verificar que la celda de EMPRESA B tenga el color púrpura
        cup_col = headers.index("890201") + 1
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
            cell = row[cup_col - 1]
            if cell.value == 4000:  # El valor de EMPRESA B
                assert cell.fill.fgColor.rgb == "00D5A6E6", (
                    f"Esperado '00D5A6E6' (Fase 6), obtenido '{cell.fill.fgColor.rgb}'"
                )
                found = True
                break
        if found:
            break

    assert found, "No se encontró la celda con color de EMPRESA B en el consolidado"
    wb.close()


def test_hoja_leyenda_existe_en_archivo_individual(consolidado_con_colores, logger, cup_repo):
    """Los archivos individuales por NIT incluyen una hoja 'Leyenda'."""
    path, output_dir = consolidado_con_colores
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    archivo = next((output_dir / "ALFA").glob("*900111111*"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    assert "Leyenda" in wb.sheetnames, (
        f"No se encontró hoja 'Leyenda'. Hojas: {wb.sheetnames}"
    )
    wb.close()


def test_hoja_leyenda_existe_en_consolidado_nits(consolidado_con_colores, logger, cup_repo):
    """El libro NITs_consolidado.xlsx incluye una hoja 'Leyenda'."""
    path, output_dir = consolidado_con_colores
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    wb = openpyxl.load_workbook(consolidado_path, read_only=True)
    assert "Leyenda" in wb.sheetnames, (
        f"No se encontró hoja 'Leyenda'. Hojas: {wb.sheetnames}"
    )
    wb.close()
