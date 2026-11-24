"""T1-T6, T10: lectura de la plantilla con la conversión de pandas (dtype=str)."""
from datetime import datetime

import openpyxl
import pytest

from src.odooInjection.infrastructure.persistence.xlsx_pre_invoice_source import (
    XlsxPreInvoiceSource,
    a_numero,
    leer_hoja_como_pandas,
)
from tests.fakes.fake_logger import FakeLogger

ENCABEZADOS = ["Base", "NIT", "Empresa", "Ciudad", "Sede", "Paciente", "N° Identificación",
               "Ingreso N°", "Empresa Misión", "Fecha Ingreso", "Tipo Examen", "Cargo",
               "Observaciones Ingreso", "Total", 890201, "890202-1"]


def _libro(ruta, filas, encabezados=ENCABEZADOS):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BASE GENERAL"
    ws.append(["nombres de examen"])
    ws.append(encabezados)
    for f in filas:
        ws.append(f)
    wb.create_sheet("Leyenda").append(["no se lee"])
    wb.save(ruta)
    return ruta


def _fila(cambios=None):
    base = dict(zip(ENCABEZADOS, ["IMEDICAL OCTUBRE 1-20", 900111111, "EMPRESA ALFA SAS", "CALI", "SEDE",
                                  "PACIENTE UNO", 1012345678, 77, None, "05/10/2026", "INGRESO", None,
                                  None, 2, 1, None]))
    base.update(cambios or {})
    return [base[h] for h in ENCABEZADOS]


def test_t1_t3_lee_por_nombre_y_detecta_examenes_por_forma(tmp_path):
    ruta = _libro(tmp_path / "pre_factura_900111111_A.xlsx", [_fila()])
    filas, cols, n = XlsxPreInvoiceSource(FakeLogger()).read(ruta)
    assert cols == ["890201", "890202-1"] and n == 1
    f = filas[0]
    assert (f["NIT"], f["Ciudad"], f["N Identificacion"], f["Ingreso"]) == ("900111111", "CALI", "1012345678", "77")
    assert f["890201"] == 1.0 and f["890202-1"] is None
    assert f["Base"] == "IMEDICAL OCTUBRE 1-20"


def test_t1_falta_columna_requerida_rechaza_el_archivo(tmp_path):
    encabezados = [h for h in ENCABEZADOS if h != "NIT"]
    ruta = _libro(tmp_path / "sin_nit.xlsx", [], encabezados)
    with pytest.raises(ValueError, match="La plantilla cambio: faltan las columnas NIT"):
        XlsxPreInvoiceSource(FakeLogger()).read(ruta)


def test_t2_falta_columna_opcional_solo_avisa(tmp_path):
    encabezados = [h for h in ENCABEZADOS if h != "Cargo"]
    ruta = _libro(tmp_path / "x.xlsx", [], encabezados)
    logger = FakeLogger()
    XlsxPreInvoiceSource(logger).read(ruta)
    assert any("faltan columnas no criticas (Cargo)" in w for w in logger.warnings)


def test_t3_quita_sufijo_literal_punto_cero():
    assert a_numero("$12,500") == 12500.0
    assert a_numero("X") == 1


def test_t4_t5_vacios_ceros_y_textos_nulos_de_pandas(tmp_path):
    ruta = _libro(tmp_path / "x.xlsx", [_fila({890201: 0, "Ciudad": "NA", "Sede": "  "}),
                                        _fila({890201: "$1,500", "890202-1": "0.0"})])
    filas, _, _ = XlsxPreInvoiceSource(FakeLogger()).read(ruta)
    assert filas[0]["890201"] is None              # 0 no es examen
    assert filas[0]["Ciudad"] is None              # "NA" es nulo para pandas
    assert filas[0]["Sede"] is None                # solo espacios
    assert filas[1]["890201"] == 1500.0 and filas[1]["890202-1"] is None


def test_lectura_como_pandas_numeros_fechas_y_recorte(tmp_path):
    ruta = tmp_path / "x.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["a", 1.0, 1.5, datetime(2026, 10, 5), True, None])
    ws.append([None, None])
    ws.append([])
    wb.save(ruta)
    # Igual que pd.read_excel(header=None, dtype=str): las filas vacías del final se recortan.
    assert leer_hoja_como_pandas(ruta) == [["a", "1", "1.5", "2026-10-05 00:00:00", "True"]]


def test_t10_lista_solo_xlsx_del_primer_nivel_ordenados(tmp_path):
    for nombre in ("b.xlsx", "a.xlsx", "~$a.xlsx", "NITs_consolidado.xlsx", "c.csv"):
        (tmp_path / nombre).write_bytes(b"")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "d.xlsx").write_bytes(b"")
    assert [p.name for p in XlsxPreInvoiceSource(FakeLogger()).list_files(tmp_path)] == ["a.xlsx", "b.xlsx"]


def test_archivo_que_no_es_excel_da_el_mismo_error_que_pandas(tmp_path):
    ruta = tmp_path / "roto.xlsx"
    ruta.write_text("no es un zip")
    with pytest.raises(ValueError, match="Excel file format cannot be determined"):
        XlsxPreInvoiceSource(FakeLogger()).read(ruta)
