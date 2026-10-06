"""Tests para CupNoveltiesLogGenerator: logs/novedades_cups.xlsx.

Sigue el mismo patrón que DuplicateCompaniesLogGenerator (tmp_path + FakeLogger
+ relectura con openpyxl). Ver specs/005_correccion-cups-por-nombre/plan.md 3.6.
"""
import openpyxl

from src.dataProcessing.domain.entities.cup_novelty import (
    CupNovelty,
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
    ESTADO_NO_CORREGIDO,
    ESTADO_CRUCE_CUP_VALOR,
    FASE_NOMBRE,
    FASE_COOCURRENCIA,
    FASE_SUGERENCIA,
    FASE_SWAP,
)
from src.dataProcessing.infrastructure.reporting.cup_novelties_log_generator import (
    CupNoveltiesLogGenerator,
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


def test_filename_is_novedades_cups():
    assert CupNoveltiesLogGenerator.FILENAME == "novedades_cups.xlsx"


def test_generate_writes_row_with_all_fields(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())
    novelties = [
        CupNovelty(
            hoja="TarifasEspeciales", cup_original="10042", examen="PROTECCION AUDITIVA",
            cup_corregido="100042", detalle="PROTECCION AUDITIVA",
            estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE,
            filas=16, contratos=["S & M OUTSOURCING S.A.S. 2026"],
        )
    ]

    log_path = gen.generate(novelties, tmp_path)

    rows = _rows(log_path)
    assert len(rows) == 1
    row = rows[0]
    assert row[1] == "TarifasEspeciales"
    assert row[2] == "10042"
    assert row[3] == "PROTECCION AUDITIVA"
    assert row[4] == "100042"
    assert row[5] == "PROTECCION AUDITIVA"
    assert row[6] == ESTADO_CORREGIDO_NOMBRE
    assert row[7] == FASE_NOMBRE
    assert row[8] == 16
    assert "S & M OUTSOURCING S.A.S. 2026" in row[9]


def test_generate_writes_total_row_at_the_end(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())
    novelties = [
        CupNovelty(hoja="Paquetes", cup_original="1", examen="E1", cup_corregido="2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=1),
        CupNovelty(hoja="Paquetes", cup_original="3", examen="E2", cup_corregido=None,
                   detalle="", estado=ESTADO_NO_CORREGIDO, fase="", filas=1),
    ]

    log_path = gen.generate(novelties, tmp_path)

    wb = openpyxl.load_workbook(log_path, data_only=True)
    ws = wb.active
    last_row = [ws.cell(ws.max_row, c).value for c in range(1, 11)]
    wb.close()
    assert "TOTAL" in str(last_row)


def test_generate_empty_novelties_writes_header_only(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())

    log_path = gen.generate([], tmp_path)

    assert log_path.exists()
    assert _rows(log_path) == []


def test_generate_does_not_merge_with_previous_run(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())
    primera = [
        CupNovelty(hoja="Paquetes", cup_original="1", examen="E1", cup_corregido="2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=1)
    ]
    gen.generate(primera, tmp_path)

    log_path = gen.generate([], tmp_path)

    assert _rows(log_path) == []


def test_generate_orders_corrected_before_suggestions_before_unresolved(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())
    novelties = [
        CupNovelty(hoja="P", cup_original="A", examen="EA", cup_corregido=None,
                   detalle="", estado=ESTADO_NO_CORREGIDO, fase="", filas=1),
        CupNovelty(hoja="P", cup_original="B", examen="EB", cup_corregido=None,
                   detalle="sugerencia: X", estado=ESTADO_NO_CORREGIDO_SUGERENCIA,
                   fase=FASE_SUGERENCIA, filas=1),
        CupNovelty(hoja="P", cup_original="C", examen="EC", cup_corregido="C2",
                   detalle="", estado=ESTADO_CORREGIDO_COOCURRENCIA,
                   fase=FASE_COOCURRENCIA, filas=1),
    ]

    log_path = gen.generate(novelties, tmp_path)

    estados = [row[6] for row in _rows(log_path)]
    assert estados == [
        ESTADO_CORREGIDO_COOCURRENCIA,
        ESTADO_NO_CORREGIDO_SUGERENCIA,
        ESTADO_NO_CORREGIDO,
    ]


def test_generate_orders_by_filas_descending_within_group(tmp_path):
    gen = CupNoveltiesLogGenerator(FakeLogger())
    novelties = [
        CupNovelty(hoja="P", cup_original="A", examen="EA", cup_corregido="A2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=2),
        CupNovelty(hoja="P", cup_original="B", examen="EB", cup_corregido="B2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=34),
    ]

    log_path = gen.generate(novelties, tmp_path)

    cups_originales = [row[2] for row in _rows(log_path)]
    assert cups_originales == ["B", "A"]


def test_generate_logs_dual_summary_by_fase(tmp_path):
    logger = FakeLogger()
    gen = CupNoveltiesLogGenerator(logger)
    novelties = [
        CupNovelty(hoja="P", cup_original="1", examen="E1", cup_corregido="2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=75),
        CupNovelty(hoja="P", cup_original="3", examen="E2", cup_corregido="4",
                   detalle="", estado=ESTADO_CRUCE_CUP_VALOR, fase=FASE_SWAP, filas=1),
        CupNovelty(hoja="P", cup_original="5", examen="E3", cup_corregido=None,
                   detalle="", estado=ESTADO_NO_CORREGIDO, fase="", filas=4),
    ]

    gen.generate(novelties, tmp_path)

    # warning agregado con el conteo de corregidos (F0+F1 aqui = 76 filas)
    assert logger.warnings
    assert any("76" in w for w in logger.warnings)
    # error agregado con el conteo de no corregidos (4 filas)
    assert logger.errors
    assert any("4" in e for e in logger.errors)


def test_generate_logs_user_msg_names_the_report_file(tmp_path):
    logger = FakeLogger()
    gen = CupNoveltiesLogGenerator(logger)
    novelties = [
        CupNovelty(hoja="P", cup_original="1", examen="E1", cup_corregido="2",
                   detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE, filas=1),
    ]

    gen.generate(novelties, tmp_path)

    assert any("novedades_cups.xlsx" in call for call in logger.warnings)  # nombre tecnico tambien lo menciona


def test_generate_no_novelties_logs_informative_message(tmp_path):
    logger = FakeLogger()
    gen = CupNoveltiesLogGenerator(logger)

    gen.generate([], tmp_path)

    assert logger.infos
    assert not logger.warnings
    assert not logger.errors
