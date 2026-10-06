"""Tests para TianCompaniesLogGenerator (logs/empresas_tian.xlsx)."""
import openpyxl

from src.company.domain.entities.tian_assignment import TianAssignment
from src.company.infrastructure.reporting.tian_companies_log_generator import (
    TianCompaniesLogGenerator,
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
    return rows, ws


def test_genera_archivo_con_nombre_esperado(tmp_path):
    gen = TianCompaniesLogGenerator(FakeLogger())

    log_path = gen.generate([], tmp_path)

    assert log_path.name == "empresas_tian.xlsx"
    assert log_path.exists()


def test_escribe_una_fila_por_empresa_mas_totales(tmp_path):
    gen = TianCompaniesLogGenerator(FakeLogger())
    asignaciones = [
        TianAssignment(
            nit_original="800082633",
            name_original="LABORATORIOS DERMANAT S.A.S",
            nit_tian="900293402",
            name_final="LABORATORIOS DERMANAT S.A.S(TIAN)",
            rows=5,
        ),
        TianAssignment(
            nit_original="830096484",
            name_original="CHEMICAL COACHING SERVICES SAS",
            nit_tian="900293402",
            name_final="CHEMICAL COACHING SERVICES SAS(TIAN)",
            rows=2,
        ),
    ]

    log_path = gen.generate(asignaciones, tmp_path)
    rows, ws = _rows(log_path)

    assert len(rows) == 2
    fila_dermanat = next(r for r in rows if r[1] == "800082633")
    assert fila_dermanat[2] == "LABORATORIOS DERMANAT S.A.S"
    assert fila_dermanat[3] == "900293402"
    assert fila_dermanat[4] == "LABORATORIOS DERMANAT S.A.S(TIAN)"
    assert fila_dermanat[5] == 5


def test_crea_directorio_si_no_existe(tmp_path):
    gen = TianCompaniesLogGenerator(FakeLogger())
    output_dir = tmp_path / "logs_nuevo"

    log_path = gen.generate([], output_dir)

    assert output_dir.exists()
    assert log_path.exists()


def test_lista_vacia_genera_libro_con_solo_encabezado(tmp_path):
    gen = TianCompaniesLogGenerator(FakeLogger())

    log_path = gen.generate([], tmp_path)
    rows, _ = _rows(log_path)

    assert rows == []


def test_sobrescribe_en_vez_de_fusionar_con_corrida_anterior(tmp_path):
    gen = TianCompaniesLogGenerator(FakeLogger())
    primera = [
        TianAssignment(
            nit_original="1", name_original="A", nit_tian="900293402", name_final="A(TIAN)"
        )
    ]
    segunda = [
        TianAssignment(
            nit_original="2", name_original="B", nit_tian="900293402", name_final="B(TIAN)"
        )
    ]

    gen.generate(primera, tmp_path)
    log_path = gen.generate(segunda, tmp_path)
    rows, _ = _rows(log_path)

    assert len(rows) == 1
    assert rows[0][1] == "2"
