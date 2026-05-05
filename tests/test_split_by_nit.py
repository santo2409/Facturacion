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


class FakeCupRepo:
    def __init__(self, data=None):
        self._data = data or []

    def exists(self, cup):
        return any(c["code"] == cup for c in self._data)

    def get_all_cups(self):
        return [c["code"] for c in self._data]

    def get_all(self):
        return self._data


CUPS_CATALOG = [
    {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
    {"id": 2, "code": "890301", "name": "PERFIL LIPÍDICO"},
]


@pytest.fixture
def cup_repo():
    return FakeCupRepo(CUPS_CATALOG)


@pytest.fixture
def consolidado(tmp_path):
    """Genera un CONSOLIDADO.xlsx temporal con 3 NITs y columnas CUPS."""
    path = tmp_path / "CONSOLIDADO.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado"

    header = [
        "Base", "Ingreso N°", "Sede", "Ciudad", "FACTURADOR",
        "Especial / General", "PAQUETE", "NIT", "Empresa", "Empresa Misión",
        "Medio de Pago", "Fecha Ingreso", "Tipo Examen", "Cargo", "Paciente",
        "N° Identificación", "Número de Póliza",
        "ORDEN, CENTRO DE COSTO, CECO, PET",
        "ORDEN, CENTRO DE COSTO, CECO, PET_1",
        "TIPO DE ACTIVIDAD", "Observaciones Ingreso", "Total",
        "890201", "890301", "999999",
    ]
    ws.append(header)
    # NIT 900111111 - EMPRESA A: 890201 tiene datos, 890301 tiene datos, 999999 vacío
    ws.append(["B1", "I001", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-01",
               "Tipo1", "Cargo1", "Pac1", "1001", "Pol1", "ORD1", "ORD1_1",
               "INTRA", "Obs1", 7000, 5000, 2000, None])
    ws.append(["B1", "I002", "S1", "BOGOTA", "ALFA", "General", "P1",
               "900111111", "EMPRESA A", "M1", "Efectivo", "2026-01-02",
               "Tipo1", "Cargo1", "Pac2", "1002", "Pol2", "ORD2", "ORD2_1",
               "INTRA", "Obs2", 4000, 3000, 1000, None])
    # NIT 900222222 - EMPRESA B: 890201 tiene datos, 890301 vacío, 999999 vacío
    ws.append(["B2", "I003", "S2", "MEDELLIN", "BETA", "Especial", "P2",
               "900222222", "EMPRESA B", "M2", "Tarjeta", "2026-01-03",
               "Tipo2", "Cargo2", "Pac3", "1003", "Pol3", "ORD3", "ORD3_1",
               "EXTRA", "Obs3", 4000, 4000, None, None])
    # NIT 900333333 - EMPRESA C: todos CUPS con datos
    ws.append(["B3", "I004", "S3", "CALI", "GENERAL", "General", "P3",
               "900333333", "EMPRESA C", "M3", "Efectivo", "2026-01-04",
               "Tipo3", "Cargo3", "Pac4", "1004", "Pol4", "ORD4", "ORD4_1",
               "INTRA", "Obs4", 1500, 1000, 500, None])

    wb.save(path)
    return path, tmp_path


def test_genera_archivos_por_nit(consolidado, logger, cup_repo):
    """3 NITs distintos → genera 3 archivos en NITs/."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    assert nits_dir.exists()
    archivos = list(nits_dir.glob("*.xlsx"))
    assert len(archivos) == 3


def test_nombre_archivo_incluye_nit_y_empresa(consolidado, logger, cup_repo):
    """Archivos se nombran pre_factura_<NIT>_<EMPRESA>.xlsx."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    nombres = sorted(f.name for f in nits_dir.glob("*.xlsx"))
    assert any("pre_factura_900111111_EMPRESA A" in n for n in nombres)
    assert any("pre_factura_900222222_EMPRESA B" in n for n in nombres)
    assert any("pre_factura_900333333_EMPRESA C" in n for n in nombres)


def test_suma_filas_igual_al_consolidado(consolidado, logger, cup_repo):
    """La suma de filas de archivos separados == filas del consolidado."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    total_filas = 0
    for archivo in nits_dir.glob("*.xlsx"):
        wb = openpyxl.load_workbook(archivo, read_only=True)
        ws = wb.active
        # Datos empiezan en fila 3 (fila 1=nombres, fila 2=headers)
        filas = sum(1 for _ in ws.iter_rows(min_row=3, values_only=True))
        total_filas += filas
        wb.close()

    assert total_filas == 4


def test_fila_superior_contiene_nombre_cups(consolidado, logger, cup_repo):
    """La fila 1 del Excel tiene el nombre del examen en columnas CUPS."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_a = next(f for f in nits_dir.glob("*.xlsx") if "900111111" in f.name)
    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    fila1 = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    wb.close()

    assert "HEMOGRAMA" in fila1
    assert "PERFIL LIPÍDICO" in fila1


def test_fila_superior_vacia_en_columnas_fijas(consolidado, logger, cup_repo):
    """Las columnas fijas en fila 1 están vacías (None)."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_a = next(f for f in nits_dir.glob("*.xlsx") if "900111111" in f.name)
    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    fila1 = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    wb.close()

    # Las primeras 22 columnas (fijas) deben ser None
    fixed_values = [v for v in fila1[:22] if v is not None]
    assert fixed_values == []


def test_headers_en_fila_dos(consolidado, logger, cup_repo):
    """La fila 2 contiene los headers originales (códigos CUPS)."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_a = next(f for f in nits_dir.glob("*.xlsx") if "900111111" in f.name)
    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    fila2 = [cell.value for cell in next(ws.iter_rows(min_row=2, max_row=2))]
    wb.close()

    assert "NIT" in fila2
    assert "Empresa" in fila2
    assert "890201" in fila2


def test_datos_empiezan_en_fila_tres(consolidado, logger, cup_repo):
    """Los datos reales están a partir de fila 3."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_a = next(f for f in nits_dir.glob("*.xlsx") if "900111111" in f.name)
    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    fila3 = [cell.value for cell in next(ws.iter_rows(min_row=3, max_row=3))]
    wb.close()

    assert "900111111" in [str(v) for v in fila3 if v is not None]


def test_cups_vacias_eliminadas_por_grupo(consolidado, logger, cup_repo):
    """CUPS 999999 vacía para todos los NITs → no aparece en ningún archivo."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    for archivo in nits_dir.glob("*.xlsx"):
        wb = openpyxl.load_workbook(archivo, read_only=True)
        ws = wb.active
        fila2 = [cell.value for cell in next(ws.iter_rows(min_row=2, max_row=2))]
        wb.close()
        assert "999999" not in fila2


def test_cups_vacia_solo_para_un_nit(consolidado, logger, cup_repo):
    """CUPS 890301 vacía para NIT 900222222 → no aparece en su archivo."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_b = next(f for f in nits_dir.glob("*.xlsx") if "900222222" in f.name)
    wb = openpyxl.load_workbook(archivo_b, read_only=True)
    ws = wb.active
    fila2 = [cell.value for cell in next(ws.iter_rows(min_row=2, max_row=2))]
    wb.close()

    assert "890201" in fila2
    assert "890301" not in fila2


def test_genera_libro_consolidado_con_hojas(consolidado, logger, cup_repo):
    """Genera NITs_consolidado.xlsx con una hoja por NIT."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    assert consolidado_path.exists()

    wb = openpyxl.load_workbook(consolidado_path, read_only=True)
    assert len(wb.sheetnames) == 3
    wb.close()


def test_nit_con_multiples_filas_agrupa_correctamente(consolidado, logger, cup_repo):
    """NIT 900111111 tiene 2 filas → su archivo debe tener 2 filas de datos."""
    path, output_dir = consolidado
    SplitByNit(logger, cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_a = next(f for f in nits_dir.glob("*.xlsx") if "900111111" in f.name)
    wb = openpyxl.load_workbook(archivo_a, read_only=True)
    ws = wb.active
    filas = sum(1 for _ in ws.iter_rows(min_row=3, values_only=True))
    wb.close()
    assert filas == 2


# ── Tests de integración end-to-end ─────────────────────────────────────


@pytest.fixture
def consolidado_e2e(tmp_path):
    """Consolidado con columnas fijas parciales, CUPS mixtas, y filas sin NIT."""
    path = tmp_path / "CONSOLIDADO.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado"

    header = [
        "Base", "Ingreso N°", "Sede", "Ciudad", "FACTURADOR",
        "Especial / General", "PAQUETE", "NIT", "Empresa", "Empresa Misión",
        "Medio de Pago", "Fecha Ingreso", "Tipo Examen", "Cargo", "Paciente",
        "N° Identificación", "Número de Póliza",
        "ORDEN, CENTRO DE COSTO, CECO, PET",
        "ORDEN, CENTRO DE COSTO, CECO, PET_1",
        "TIPO DE ACTIVIDAD", "Observaciones Ingreso", "Total",
        "100004", "860205-1", "777777",
    ]
    ws.append(header)
    # NIT 800111 con datos en 100004 y 860205-1, 777777 vacío
    ws.append(["B", "I1", "S", "BOG", "F", "G", "P", "800111", "EMP_X", "M",
               "E", "2026-01-01", "T", "C", "P", "ID", "POL", "O", "O1",
               "INTRA", "OBS", 100, 50, 30, None])
    # NIT 800222 con datos solo en 100004, 860205-1 y 777777 vacíos
    ws.append(["B", "I2", "S", "MED", "F", "G", "P", "800222", "EMP_Y", "M",
               "E", "2026-01-02", "T", "C", "P", "ID", "POL", "O", "O1",
               "EXTRA", "OBS", 200, 70, None, None])
    # Fila sin NIT → debe omitirse
    ws.append(["B", "I3", "S", "CAL", "F", "G", "P", None, "EMP_Z", "M",
               "E", "2026-01-03", "T", "C", "P", "ID", "POL", "O", "O1",
               "INTRA", "OBS", 50, 10, 5, None])

    wb.save(path)
    return path, tmp_path


@pytest.fixture
def partial_cup_repo():
    """Repo con solo algunos CUPS en catálogo (100004 sí, 860205-1 no)."""
    return FakeCupRepo([
        {"id": 1, "code": "100004", "name": "PERFIL LIPÍDICO"},
    ])


def test_e2e_cups_vacias_eliminadas_nombres_presentes(consolidado_e2e, logger, partial_cup_repo):
    """Flujo completo: CUPS vacías eliminadas, nombres presentes donde existen."""
    path, output_dir = consolidado_e2e
    SplitByNit(logger, partial_cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivos = list(nits_dir.glob("*.xlsx"))
    # Solo 2 archivos (la fila sin NIT se omite)
    assert len(archivos) == 2

    # Verificar archivo de NIT 800111
    archivo_x = next(f for f in archivos if "800111" in f.name)
    wb = openpyxl.load_workbook(archivo_x, read_only=True)
    ws = wb.active
    fila1 = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    fila2 = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    wb.close()

    # 100004 tiene nombre, 860205-1 no tiene nombre en catálogo
    assert "PERFIL LIPÍDICO" in fila1
    assert "100004" in fila2
    assert "860205-1" in fila2
    # 777777 vacía → eliminada
    assert "777777" not in fila2


def test_e2e_cups_sin_nombre_en_catalogo_celda_vacia(consolidado_e2e, logger, partial_cup_repo):
    """CUPS sin nombre en catálogo → celda vacía en fila de nombres."""
    path, output_dir = consolidado_e2e
    SplitByNit(logger, partial_cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo_x = next(f for f in nits_dir.glob("*.xlsx") if "800111" in f.name)
    wb = openpyxl.load_workbook(archivo_x, read_only=True)
    ws = wb.active
    fila1 = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    fila2 = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    wb.close()

    # Encontrar posición de 860205-1 en fila2
    idx_860 = fila2.index("860205-1")
    # Su nombre en fila1 debe ser vacío (None o "")
    assert fila1[idx_860] in (None, "")


def test_e2e_nit_ausente_se_omite(consolidado_e2e, logger, partial_cup_repo, caplog):
    """Filas sin NIT no generan archivo y se loguea warning."""
    path, output_dir = consolidado_e2e
    with caplog.at_level(logging.WARNING):
        SplitByNit(logger, partial_cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivos = list(nits_dir.glob("*.xlsx"))
    assert len(archivos) == 2
    assert "sin NIT" in caplog.text.lower() or "sin nit" in caplog.text.lower()


def test_e2e_libro_consolidado_coherente(consolidado_e2e, logger, partial_cup_repo):
    """El libro consolidado tiene una hoja por NIT válido."""
    path, output_dir = consolidado_e2e
    SplitByNit(logger, partial_cup_repo).execute(path, output_dir)

    consolidado_path = output_dir / "NITs_consolidado.xlsx"
    assert consolidado_path.exists()
    wb = openpyxl.load_workbook(consolidado_path, read_only=True)
    assert len(wb.sheetnames) == 2
    wb.close()


def test_e2e_columnas_fijas_en_orden(consolidado_e2e, logger, partial_cup_repo):
    """Las columnas fijas aparecen en el orden definido por FIXED_COLUMNS."""
    from src.preInvoice.application.use_cases.split_by_nit import FIXED_COLUMNS

    path, output_dir = consolidado_e2e
    SplitByNit(logger, partial_cup_repo).execute(path, output_dir)

    nits_dir = output_dir / "NITs"
    archivo = next(nits_dir.glob("*.xlsx"))
    wb = openpyxl.load_workbook(archivo, read_only=True)
    ws = wb.active
    fila2 = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    wb.close()

    # Extraer solo las columnas fijas del output (las que están en FIXED_COLUMNS)
    fixed_in_output = [c for c in fila2 if c in FIXED_COLUMNS]
    # Deben estar en el mismo orden que FIXED_COLUMNS
    expected_order = [c for c in FIXED_COLUMNS if c in fixed_in_output]
    assert fixed_in_output == expected_order
