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
        result = _reporter(tmp_path).write({"sin_resolver": []}, [])

        assert result is None
        assert not (tmp_path / "asignar_tarifas").exists()

    def test_folder_name_uses_clock_format(self, tmp_path):
        folder = _reporter(tmp_path).write({"sin_resolver": [_finding()]}, [])

        assert folder == tmp_path / "asignar_tarifas" / "2026-10-10_1430"

    def test_columns_match_rf10(self, tmp_path):
        folder = _reporter(tmp_path).write({"sin_resolver": [_finding()]}, [])

        df = pl.read_excel(folder / "sin_resolver.xlsx")

        assert df.columns == [
            "NIT", "Empresa", "Paciente", "N° Identificación", "Ciudad",
            "TIPO DE ACTIVIDAD", "CUP", "Precio asignado", "Origen",
        ]

    def test_one_row_per_patient_cup(self, tmp_path):
        rows = [_finding(cup="890201"), _finding(cup="890202"), _finding(cup="890201", patient="ANA")]

        folder = _reporter(tmp_path).write({"fase_02_paquete_c_2025": rows}, [])

        df = pl.read_excel(folder / "fase_02_paquete_c_2025.xlsx")
        assert df.height == 3
        assert df["CUP"].cast(pl.Utf8).to_list() == ["890201", "890202", "890201"]

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
