"""Tests para NotFoundCompaniesLogGenerator."""
import openpyxl

from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.reporting.not_found_companies_log_generator import (
    ESTADO_FALTA_ODOO,
    ESTADO_NIT_CORREGIDO,
    ESTADO_NO_ENCONTRADO,
    ESTADO_NOMBRE_CORREGIDO,
    NotFoundCompaniesLogGenerator,
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


def test_generate_only_includes_companies_not_found_anywhere(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult("111", True, "EMPRESA ENCONTRADA", checked_bases="Odoo"),
        NitResult("222", False, checked_bases="Odoo, RUES"),
        NitResult("333", False, checked_bases="RUES"),
    ]

    log_path = gen.generate(resultados, tmp_path)

    rows = {row[1]: row for row in _rows(log_path)}
    assert set(rows) == {"222", "333"}
    assert rows["222"][2] in ("", None)
    assert rows["222"][3] == ESTADO_NO_ENCONTRADO
    assert rows["222"][4] == "Odoo, RUES"
    assert rows["333"][3] == ESTADO_NO_ENCONTRADO
    assert rows["333"][4] == "RUES"


def test_generate_keeps_found_via_rues_without_odoo_as_pending(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult("222", True, "EMPRESA RUES", checked_bases="Odoo, RUES"),
    ]

    log_path = gen.generate(resultados, tmp_path)

    rows = {row[1]: row for row in _rows(log_path)}
    assert set(rows) == {"222"}
    assert rows["222"][2] == "EMPRESA RUES"
    assert rows["222"][3] == ESTADO_FALTA_ODOO


def test_generate_removes_entry_found_directly_in_odoo_or_local_cache(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())

    gen.generate([NitResult("111", True, "EMPRESA RUES", checked_bases="Odoo, RUES")], tmp_path)
    log_path = gen.generate(
        [NitResult("111", True, "EMPRESA EN ODOO", checked_bases="Odoo")], tmp_path
    )

    assert _rows(log_path) == []

    gen.generate([NitResult("222", True, "EMPRESA RUES 2", checked_bases="Odoo, RUES")], tmp_path)
    log_path = gen.generate(
        [NitResult("222", True, "EMPRESA CACHEADA", checked_bases="BD local")], tmp_path
    )

    assert _rows(log_path) == []


def test_generate_with_no_pending_nits_produces_empty_report(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [NitResult("111", True, "EMPRESA ENCONTRADA", checked_bases="Odoo")]

    log_path = gen.generate(resultados, tmp_path)

    assert _rows(log_path) == []


def test_generate_accumulates_not_found_across_runs(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())

    gen.generate([NitResult("111", False, checked_bases="Odoo, RUES")], tmp_path)
    gen.generate([NitResult("222", False, checked_bases="RUES")], tmp_path)

    rows = _rows(tmp_path / NotFoundCompaniesLogGenerator.FILENAME)
    assert {r[1] for r in rows} == {"111", "222"}


def test_generate_removes_entry_once_resolved(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())

    gen.generate([NitResult("111", False, checked_bases="Odoo, RUES")], tmp_path)
    gen.generate(
        [NitResult("111", True, "EMPRESA YA RESUELTA", checked_bases="Odoo")], tmp_path
    )

    rows = _rows(tmp_path / NotFoundCompaniesLogGenerator.FILENAME)
    assert rows == []


def test_generate_logs_pending_count_for_user(tmp_path):
    logger = FakeLogger()
    gen = NotFoundCompaniesLogGenerator(logger)

    gen.generate([NitResult("111", False, checked_bases="Odoo, RUES")], tmp_path)

    assert logger.infos
    assert "1" in logger.infos[0]


def test_generate_migrates_old_five_column_format(tmp_path):
    log_path = tmp_path / NotFoundCompaniesLogGenerator.FILENAME
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["#", "NIT", "Empresa", "Base Consultada", "Fecha/Hora"])
    ws.append([1, "555", "", "RUES", "2026-01-01 00:00:00"])
    wb.save(log_path)

    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    gen.generate([NitResult("666", False, checked_bases="Odoo, RUES")], tmp_path)

    rows = {row[1]: row for row in _rows(log_path)}
    assert set(rows) == {"555", "666"}
    assert rows["555"][3] == ESTADO_NO_ENCONTRADO


def _estado(log_path, nit):
    return {row[1]: row for row in _rows(log_path)}[nit][3]


# ── T22: estados compuestos ──────────────────────────────────────────────────


def test_nit_correction_state_includes_both_nits(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult(
            "900111222", True, "EMPRESA A SAS", checked_bases="Odoo, RUES",
            source="RUES/nombre", nit_original="900111111",
        )
    ]

    log_path = gen.generate(resultados, tmp_path)

    estado = _estado(log_path, "900111222")
    assert ESTADO_NIT_CORREGIDO in estado
    assert "900111111" in estado
    assert "900111222" in estado


def test_name_correction_state_includes_both_names(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult(
            "111", True, "EMPRESA NUEVA SAS", checked_bases="Odoo, RUES",
            source="RUES/NIT", name_original="EMPRESA VIEJA",
        )
    ]

    log_path = gen.generate(resultados, tmp_path)

    estado = _estado(log_path, "111")
    assert ESTADO_NOMBRE_CORREGIDO in estado
    assert "EMPRESA VIEJA" in estado
    assert "EMPRESA NUEVA SAS" in estado


def test_conflict_state_is_registered(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult(
            "111", True, "EMPRESA A", checked_bases="Odoo",
            conflict="Nombre ya registrado en BD local con otro NIT",
        )
    ]

    log_path = gen.generate(resultados, tmp_path)

    assert ESTADO_CONFLICTO_BD_LOCAL in _estado(log_path, "111")


def test_combined_state_keeps_falta_odoo_and_correction(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult(
            "900111222", True, "EMPRESA RUES", checked_bases="Odoo, RUES",
            source="RUES/nombre", nit_original="900111111",
        )
    ]

    log_path = gen.generate(resultados, tmp_path)

    estado = _estado(log_path, "900111222")
    assert estado.startswith(ESTADO_FALTA_ODOO)
    assert ESTADO_NIT_CORREGIDO in estado
    assert " | " in estado


def test_state_is_byte_identical_without_novelty_fields(tmp_path):
    """No regresión: los otros consumidores no construyen los campos nuevos."""
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult("222", False, checked_bases="Odoo, RUES"),
        NitResult("333", True, "EMPRESA RUES", checked_bases="Odoo, RUES"),
    ]

    log_path = gen.generate(resultados, tmp_path)

    assert _estado(log_path, "222") == ESTADO_NO_ENCONTRADO
    assert _estado(log_path, "333") == ESTADO_FALTA_ODOO


def test_not_found_with_name_correction_keeps_both_parts(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult("999", False, "EMPRESA DEL LIBRO", checked_bases="Odoo, RUES")
    ]

    log_path = gen.generate(resultados, tmp_path)

    assert _estado(log_path, "999") == ESTADO_NO_ENCONTRADO


# ── T23: ciclo de vida de la novedad ─────────────────────────────────────────


def test_correction_row_persists_when_company_is_resolved(tmp_path):
    """Una empresa resuelta pero corregida sigue requiriendo acción manual."""
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    resultados = [
        NitResult(
            "900111222", True, "EMPRESA A", checked_bases="Odoo",
            source="Odoo/nombre", nit_original="900111111",
        )
    ]

    log_path = gen.generate(resultados, tmp_path)

    assert [r[1] for r in _rows(log_path)] == ["900111222"]


def test_resolved_without_novelty_is_removed(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())

    log_path = gen.generate(
        [NitResult("111", True, "EMPRESA A", checked_bases="Odoo")], tmp_path
    )

    assert _rows(log_path) == []


def test_correction_row_disappears_on_clean_rerun(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    gen.generate(
        [
            NitResult(
                "900111222", True, "EMPRESA A", checked_bases="Odoo",
                source="Odoo/nombre", nit_original="900111111",
            )
        ],
        tmp_path,
    )

    log_path = gen.generate(
        [NitResult("900111222", True, "EMPRESA A", checked_bases="Odoo")], tmp_path
    )

    assert _rows(log_path) == []


def test_composite_state_round_trips_through_previous_history(tmp_path):
    gen = NotFoundCompaniesLogGenerator(FakeLogger())
    gen.generate(
        [
            NitResult(
                "900111222", True, "EMPRESA RUES", checked_bases="Odoo, RUES",
                source="RUES/nombre", nit_original="900111111",
            )
        ],
        tmp_path,
    )

    log_path = gen.generate([NitResult("777", False, checked_bases="RUES")], tmp_path)

    estado = _estado(log_path, "900111222")
    assert estado.startswith(ESTADO_FALTA_ODOO)
    assert ESTADO_NIT_CORREGIDO in estado


def test_read_previous_warns_instead_of_silently_returning_empty(tmp_path):
    log_path = tmp_path / NotFoundCompaniesLogGenerator.FILENAME
    log_path.write_bytes(b"esto no es un archivo xlsx valido")
    logger = FakeLogger()
    gen = NotFoundCompaniesLogGenerator(logger)

    gen.generate([NitResult("444", False, checked_bases="Odoo, RUES")], tmp_path)

    rows = _rows(log_path)
    assert [r[1] for r in rows] == ["444"]
    assert logger.warnings
