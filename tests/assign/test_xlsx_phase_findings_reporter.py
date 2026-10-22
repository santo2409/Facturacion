from datetime import datetime
from pathlib import Path

import polars as pl

from src.assign.infrastructure.reporting.xlsx_phase_findings_reporter import (
    XlsxPhaseFindingsReporter,
)
from tests.fakes.fake_phase_findings_reporter import FakePhaseFindingsReporter

_CLOCK = lambda: datetime(2026, 10, 10, 14, 30)  # noqa: E731

PHASE1 = "fase_01_paquete_propio_local"
PHASE2 = "fase_02_paquete_c_2025"
PHASE4 = "fase_04_cup_base_paquete_c"
PHASE6 = "fase_06_cualquier_ciudad"
SIN_RESOLVER = "sin_resolver"
EXPIRED = "odoo_tarifa_vencida"

_PHASE_COLUMNS = [
    "Fase", "Empresa", "NIT", "Paquete original", "Ciudad original", "CUP original",
    "Actividad", "Tarifa asignada", "Fuente de la tarifa", "Ciudad efectiva",
    "CUP efectivo", "Nº pacientes", "Qué debe hacer el área",
]


def _finding(
    cup="890201", price=7500, patient="JUAN", phase="Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)",
    source_type="Paquete", source="PAQUETE C 2025", city="BOGOTA, D.C.", city_eff="BOGOTA, D.C.",
    cup_eff=None, package="PAQUETE BASICO",
):
    return {
        "NIT": "900111111",
        "Empresa": "EMPRESA A",
        "Paciente": patient,
        "N° Identificación": f"id-{patient}",
        "Ciudad": city,
        "TIPO DE ACTIVIDAD": "INTRA",
        "CUP": cup,
        "Precio asignado": price,
        "Origen": source,
        "Fase": phase,
        "Paquete original": package,
        "Tipo de fuente": source_type,
        "Fuente": source,
        "Ciudad efectiva": city_eff,
        "CUP efectivo": cup_eff or cup,
    }


def _unresolved(cup="890201", patient="JUAN"):
    return _finding(
        cup=cup, price=1, patient=patient, phase="Sin resolver",
        source_type=None, source="Sin tarifa", city_eff=None, cup_eff="",
    ) | {"CUP efectivo": None}


def _expired(patient="JUAN", price=31100):
    return {
        "NIT": "900111111", "Empresa": "EMPRESA A", "Paciente": patient,
        "N° Identificación": f"id-{patient}", "Ciudad": "BOGOTA, D.C.",
        "TIPO DE ACTIVIDAD": "INTRA", "CUP": "890201",
        "Tarifa Odoo": "GRUPO ADECCO 2026", "Tipo de tarifa": "Especial",
        "Inicio vigencia": "2025-01-01", "Fin vigencia": "2025-12-31",
        "Estado Odoo": "approved", "Precio asignado": price,
    }


def _reporter(tmp_path):
    return XlsxPhaseFindingsReporter(base_dir=tmp_path / "asignar_tarifas", clock=_CLOCK)


def _read(folder, name, sheet=None):
    kwargs = {"sheet_name": sheet} if sheet else {}
    return pl.read_excel(folder / f"{name}.xlsx", **kwargs)


class TestXlsxPhaseFindingsReporter:
    def test_writes_only_phases_with_rows(self, tmp_path):
        findings = {
            "fase_01_paquete_propio_local": [],
            PHASE2: [_finding()],
            SIN_RESOLVER: [_unresolved()],
        }

        folder = _reporter(tmp_path).write(findings, [])

        assert sorted(p.name for p in folder.iterdir()) == [
            "fase_02_paquete_c_2025.xlsx",
            "sin_resolver.xlsx",
        ]

    def test_no_folder_when_nothing_to_write(self, tmp_path):
        result = _reporter(tmp_path).write({SIN_RESOLVER: []}, [])

        assert result is None
        assert not (tmp_path / "asignar_tarifas").exists()

    def test_folder_name_uses_clock_format(self, tmp_path):
        folder = _reporter(tmp_path).write({SIN_RESOLVER: [_unresolved()]}, [])

        assert folder == tmp_path / "asignar_tarifas" / "2026-10-10_1430"

    def test_phase_book_columns(self, tmp_path):
        folder = _reporter(tmp_path).write({PHASE2: [_finding()]}, [])

        assert _read(folder, PHASE2).columns == _PHASE_COLUMNS

    def test_groups_50_patients_into_one_row(self, tmp_path):
        rows = [_finding(patient=f"P{i}") for i in range(50)]

        folder = _reporter(tmp_path).write({PHASE2: rows}, [])

        df = _read(folder, PHASE2)
        assert df.height == 1
        assert df["Nº pacientes"].to_list() == [50]
        assert "Paciente" not in df.columns and "N° Identificación" not in df.columns

    def test_different_cups_stay_in_different_rows(self, tmp_path):
        rows = [_finding(cup="890201"), _finding(cup="890202"), _finding(cup="890201", patient="ANA")]

        folder = _reporter(tmp_path).write({PHASE2: rows}, [])

        df = _read(folder, PHASE2)
        assert df["CUP original"].cast(pl.Utf8).to_list() == ["890201", "890202"]
        assert df["Nº pacientes"].to_list() == [2, 1]

    def test_row_shows_original_key_and_source(self, tmp_path):
        row = _finding(
            cup="890201-1", price=4000, phase="Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)",
            cup_eff="890201",
        )

        folder = _reporter(tmp_path).write({PHASE4: [row]}, [])

        out = _read(folder, PHASE4).row(0, named=True)
        assert out["Paquete original"] == "PAQUETE BASICO"
        assert out["CUP original"] == "890201-1"
        assert out["CUP efectivo"] == "890201"
        assert out["Tarifa asignada"] == 4000
        assert out["Fuente de la tarifa"] == "Paquete: PAQUETE C 2025"
        assert "890201-1" in out["Qué debe hacer el área"]

    def test_phase6_shows_original_and_effective_city(self, tmp_path):
        row = _finding(
            city="MEDELLIN", city_eff="BOGOTA, D.C.", source_type="Proveedor", source="PROVEEDOR X",
            phase="Fase 6 — Cualquier paquete/ciudad (cup + actividad)",
        )

        folder = _reporter(tmp_path).write({PHASE6: [row]}, [])

        out = _read(folder, PHASE6).row(0, named=True)
        assert out["Ciudad original"] == "MEDELLIN"
        assert out["Ciudad efectiva"] == "BOGOTA, D.C."
        assert out["Fuente de la tarifa"] == "Proveedor: PROVEEDOR X"

    def test_phase1_says_rate_comes_from_local_db_and_asks_to_load_in_odoo(self, tmp_path):
        row = _finding(phase="Fase 1 — Paquete propio local", package="PAQUETE C 2025", source="PAQUETE C 2025")

        folder = _reporter(tmp_path).write({PHASE1: [row]}, [])

        out = _read(folder, PHASE1).row(0, named=True)
        assert out["Fuente de la tarifa"] == "Base de datos local — Paquete: PAQUETE C 2025"
        action = out["Qué debe hacer el área"]
        assert "Odoo no tiene" in action and "Cargar en Odoo" in action
        assert "PAQUETE C 2025" in action and "890201" in action

    def test_phase1_without_odoo_does_not_ask_to_load(self, tmp_path):
        row = _finding(phase="Fase 1 — Paquete propio local")

        folder = _reporter(tmp_path).write({PHASE1: [row]}, [], odoo_available=False)

        out = _read(folder, PHASE1).row(0, named=True)
        assert out["Fuente de la tarifa"] == "Base de datos local — Paquete: PAQUETE C 2025"
        assert "Odoo no estuvo disponible" in out["Qué debe hacer el área"]
        assert "Cargar en Odoo" not in out["Qué debe hacer el área"]

    def test_sin_resolver_shows_sin_tarifa_not_one(self, tmp_path):
        folder = _reporter(tmp_path).write({SIN_RESOLVER: [_unresolved()]}, [])

        out = _read(folder, SIN_RESOLVER).row(0, named=True)
        assert out["Tarifa asignada"] == "Sin tarifa"
        assert out["Fuente de la tarifa"] == "Sin tarifa"
        assert "Crear tarifa" in out["Qué debe hacer el área"]
        assert "PAQUETE BASICO" in out["Qué debe hacer el área"]

    def test_expired_book_groups_by_rate_and_key(self, tmp_path):
        rows = [_expired(patient="A"), _expired(patient="B"), _expired(patient="C", price=40000)]

        folder = _reporter(tmp_path).write({EXPIRED: rows}, [])

        df = _read(folder, EXPIRED)
        assert df.columns == [
            "Empresa", "NIT", "Tarifa Odoo", "Tipo de tarifa", "Inicio vigencia",
            "Fin vigencia", "Estado Odoo", "Ciudad", "CUP", "Actividad",
            "Tarifa asignada", "Nº pacientes", "Qué debe hacer el área",
        ]
        assert df["Nº pacientes"].to_list() == [2, 1]
        assert "GRUPO ADECCO 2026" in df["Qué debe hacer el área"][0]

    def test_every_book_has_legend_sheet(self, tmp_path):
        folder = _reporter(tmp_path).write(
            {PHASE2: [_finding()], EXPIRED: [_expired()]},
            [{"NIT": "1", "Empresa": "A", "Motivo": "No encontrada en Odoo"}],
        )

        for name in (PHASE2, EXPIRED, "empresas_odoo"):
            legend = _read(folder, name, sheet="Leyenda")
            assert legend.columns == ["Columna", "Significado"]
            assert legend["Columna"][0] == "Libro"
        assert "Nº pacientes" in _read(folder, PHASE2, sheet="Leyenda")["Columna"].to_list()

    def test_empresas_odoo_has_motivo_column(self, tmp_path):
        companies = [
            {"NIT": "111", "Empresa": "A", "Motivo": "No encontrada en Odoo"},
            {"NIT": "222", "Empresa": "B", "Motivo": "Sin tarifa especial ni base"},
        ]

        folder = _reporter(tmp_path).write({}, companies)

        df = pl.read_excel(folder / "empresas_odoo.xlsx")
        assert df.columns == ["NIT", "Empresa", "Motivo"]
        assert df["Motivo"].to_list() == ["No encontrada en Odoo", "Sin tarifa especial ni base"]

    def test_fake_captures_findings(self):
        fake = FakePhaseFindingsReporter()

        result = fake.write({"sin_resolver": [_finding()]}, [{"NIT": "1", "Empresa": "A", "Motivo": "x"}])

        assert result == Path("fake")
        assert fake.findings == {"sin_resolver": [_finding()]}
        assert fake.companies == [{"NIT": "1", "Empresa": "A", "Motivo": "x"}]
