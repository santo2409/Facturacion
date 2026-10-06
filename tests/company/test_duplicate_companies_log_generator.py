import openpyxl

from src.company.domain.entities.duplicate_candidate import DuplicateCandidate
from src.company.infrastructure.reporting.duplicate_companies_log_generator import (
    DuplicateCompaniesLogGenerator,
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


def test_generate_writes_candidate_row_with_both_names_and_reason(tmp_path):
    gen = DuplicateCompaniesLogGenerator(FakeLogger())
    candidates = [
        DuplicateCandidate(
            nit_a="901545404", name_a="LAB3 SAS",
            nit_b="901546404", name_b="LAB3 S.A.S",
            reasons=["Nombre idéntico (ignorando puntuación y espacios)"],
            similarity=0,
        )
    ]

    log_path = gen.generate(candidates, tmp_path)

    rows = _rows(log_path)
    assert len(rows) == 1
    row = rows[0]
    assert row[1] == "901545404"
    assert row[2] == "LAB3 SAS"
    assert row[3] == "901546404"
    assert row[4] == "LAB3 S.A.S"
    assert "Nombre idéntico" in row[5]


def test_generate_joins_multiple_reasons_with_separator(tmp_path):
    gen = DuplicateCompaniesLogGenerator(FakeLogger())
    candidates = [
        DuplicateCandidate(
            nit_a="83004087", name_a="COBRA S.A",
            nit_b="830040872", name_b="COBRA S A",
            reasons=["Nombre idéntico (ignorando puntuación y espacios)", "NIT difiere en el dígito final"],
            similarity=97,
        )
    ]

    log_path = gen.generate(candidates, tmp_path)

    estado = _rows(log_path)[0][5]
    assert "Nombre idéntico" in estado
    assert "NIT difiere" in estado
    assert " | " in estado


def test_generate_writes_similarity_column(tmp_path):
    gen = DuplicateCompaniesLogGenerator(FakeLogger())
    candidates = [
        DuplicateCandidate(
            nit_a="19146113", name_a="MARIO ALBERTO HUERTAS COTES",
            nit_b="191461130", name_b="HUERTAS COTES MARIO ALBERTO",
            reasons=["NIT difiere en el dígito final"], similarity=100,
        )
    ]

    log_path = gen.generate(candidates, tmp_path)

    assert _rows(log_path)[0][6] == 100


def test_generate_with_no_candidates_produces_empty_report(tmp_path):
    gen = DuplicateCompaniesLogGenerator(FakeLogger())

    log_path = gen.generate([], tmp_path)

    assert log_path.exists()
    assert _rows(log_path) == []


def test_generate_does_not_merge_with_previous_run(tmp_path):
    """A diferencia de empresas_no_encontradas.xlsx, cada corrida es un barrido
    completo: un candidato resuelto en la corrida anterior no debe persistir."""
    gen = DuplicateCompaniesLogGenerator(FakeLogger())
    primera = [
        DuplicateCandidate(
            nit_a="111", name_a="A", nit_b="222", name_b="A2",
            reasons=["Nombre idéntico (ignorando puntuación y espacios)"], similarity=0,
        )
    ]
    gen.generate(primera, tmp_path)

    log_path = gen.generate([], tmp_path)

    assert _rows(log_path) == []


def test_generate_logs_candidate_count_for_user(tmp_path):
    logger = FakeLogger()
    gen = DuplicateCompaniesLogGenerator(logger)
    candidates = [
        DuplicateCandidate(
            nit_a="111", name_a="A", nit_b="222", name_b="A2",
            reasons=["Nombre idéntico (ignorando puntuación y espacios)"], similarity=0,
        )
    ]

    gen.generate(candidates, tmp_path)

    assert logger.infos
    assert "1" in logger.infos[0]


def test_filename_is_empresas_duplicadas():
    assert DuplicateCompaniesLogGenerator.FILENAME == "empresas_duplicadas.xlsx"
