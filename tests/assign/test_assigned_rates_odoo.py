"""Tests de la opción 6 con tarifas de Odoo (spec 010)."""
import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from src.assign.application.use_cases.assigned_rates import AssignRatesFromExcel
from tests.fakes.fake_activity_repo import FakeActivityRepo
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_city_repo import FakeCityRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_odoo_repo import FakeOdooRepo
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_phase_findings_reporter import FakePhaseFindingsReporter
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo

NOT_IN_ODOO = "No encontrada en Odoo. Acción: registrar la empresa en Odoo (el sistema no la crea)."
NO_RATES_IN_ODOO = "Sin tarifa especial ni base. Acción: asignar una tarifa especial o base a la empresa en Odoo."
NIT = "830050228"
SPECIAL = {"id": 17534, "name": "GRUPO ADECCO 2026"}
BASE = {"id": 17235, "name": "Tarifa basica 2025"}


def _partner(nit=NIT, special=SPECIAL, base=BASE, name="ADECCO"):
    return {
        "nit": nit, "partner_id": 1, "name": name,
        "special_id": special["id"] if special else None,
        "special_name": special["name"] if special else None,
        "base_id": base["id"] if base else None,
        "base_name": base["name"] if base else None,
    }


def _line(rate_id, cup, price, city="BOGOTA, D.C.", intra=True):
    return {"rate_id": rate_id, "city": city, "cup": cup, "intra": intra, "price": price}


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    with open(tmp_path / "data.json", "w") as f:
        json.dump([], f)
    company_repo = FakeCompanyRepo([{"id": 1, "nit": NIT, "name": "ADECCO"}])
    company_repo._packages = [{"company": 1, "package": 1, "model": "Package"}]
    biller_company_repo = FakeBillerCompanyRepo()
    biller_company_repo._data = [{"company": 1, "biller": 1}]
    return {
        "biller_repo": FakeBillerRepo([{"id": 1, "name": "ALFA"}]),
        "company_repo": company_repo,
        "biller_company_repo": biller_company_repo,
        "package_repo": FakePackageRepo([{"id": 1, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([]),
        "special_repo": FakeSpecialRepo([]),
        "city_repo": FakeCityRepo([{"id": 1, "name": "BOGOTA, D.C."}]),
        "activities_repo": FakeActivityRepo(),
        "rates_repo": FakeRatesRepo(),
        "cup_repo": FakeCupRepo([
            {"id": 1, "code": "890201", "name": "A"},
            {"id": 2, "code": "890202", "name": "B"},
        ]),
        "fuzz": FakeFuzz(),
        "progress": FakeProgress(),
        "logger": FakeLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
    }


def _build(deps, **extra):
    return AssignRatesFromExcel(**{**deps, **extra})


def _df(nits=(NIT,), cups=("890201",)):
    data = {
        "NIT": list(nits),
        "Empresa": [f"EMPRESA {n}" for n in nits],
        "Ciudad": ["BOGOTA, D.C."] * len(nits),
        "TIPO DE ACTIVIDAD": ["INTRA"] * len(nits),
    }
    for cup in cups:
        data[cup] = [1] * len(nits)
    return pl.DataFrame(data)


class FailingOnPartnersRepo(FakeOdooRepo):
    def find_partner_rates_batch(self, nits):
        raise RuntimeError("odoo caído")


# ── T07: carga de tarifas Odoo ────────────────────────────────────────────

class TestLoadOdooRates:
    def test_odoo_rates_loaded_with_single_batch_per_port_method(self, deps):
        nits = ["111111111", "222222222", NIT]
        odoo = FakeOdooRepo(
            partner_rates=[_partner(NIT)],
            rate_lines=[_line(SPECIAL["id"], "890201", 100)],
        )
        uc = _build(deps, odoo_repo=odoo)
        df = pl.concat([_df(nits=nits) for _ in range(17)])  # 51 filas

        uc._load_odoo_rates(df)

        assert odoo.calls == {"find_partner_rates_batch": 1, "find_rate_lines": 1, "find_rate_info": 1}

    def test_company_not_in_odoo_is_reported(self, deps):
        uc = _build(deps, odoo_repo=FakeOdooRepo())

        uc._load_odoo_rates(_df(nits=["900111111"]))

        assert uc._company_findings == [
            {"NIT": "900111111", "Empresa": "EMPRESA 900111111", "Motivo": NOT_IN_ODOO}
        ]

    def test_partner_without_rates_is_reported(self, deps):
        odoo = FakeOdooRepo(partner_rates=[_partner(special=None, base=None)])
        uc = _build(deps, odoo_repo=odoo)

        uc._load_odoo_rates(_df())

        assert [f["Motivo"] for f in uc._company_findings] == [NO_RATES_IN_ODOO]
        assert odoo.calls["find_rate_lines"] == 0

    def test_company_with_rates_is_not_reported(self, deps):
        odoo = FakeOdooRepo(partner_rates=[_partner()])
        uc = _build(deps, odoo_repo=odoo)

        uc._load_odoo_rates(_df())

        assert uc._company_findings == []
        assert uc.odoo_available is True

    def test_odoo_none_skips_loading_and_no_company_report(self, deps):
        uc = _build(deps, odoo_repo=None)

        uc._load_odoo_rates(_df())

        assert uc.odoo_available is False
        assert uc._company_findings == []

    def test_connect_failure_falls_back_with_warning(self, deps):
        class FailingConnect(FakeOdooRepo):
            def connect(self):
                raise RuntimeError("sin red")

        uc = _build(deps, odoo_repo=FailingConnect())
        uc._connect_odoo()

        uc._load_odoo_rates(_df())

        assert uc.odoo_available is False
        assert uc._company_findings == []
        assert any("No se pudo conectar a Odoo" in w for w in deps["logger"].warnings)

    def test_query_failure_falls_back_to_local_with_warning(self, deps):
        uc = _build(deps, odoo_repo=FailingOnPartnersRepo())

        uc._load_odoo_rates(_df())

        assert uc.odoo_available is False
        assert uc._company_findings == []
        assert any("odoo caído" in w for w in deps["logger"].warnings)


# ── T08: columna PAQUETE ──────────────────────────────────────────────────

class TestPaqueteFromOdoo:
    def _paquete(self, deps, partner=None):
        odoo = FakeOdooRepo(partner_rates=[partner] if partner else [])
        uc = _build(deps, odoo_repo=odoo)
        df = _df()
        uc._load_odoo_rates(df)
        return uc, uc._assign_paquete(df, uc._build_lookups())

    def test_paquete_uses_special_name_when_present(self, deps):
        _, df = self._paquete(deps, _partner())

        assert df["PAQUETE"][0] == "GRUPO ADECCO 2026"

    def test_paquete_uses_base_name_when_no_special(self, deps):
        _, df = self._paquete(deps, _partner(special=None))

        assert df["PAQUETE"][0] == "Tarifa basica 2025"

    def test_paquete_falls_back_to_local_when_no_odoo_rates(self, deps):
        _, df = self._paquete(deps, _partner(special=None, base=None))

        assert df["PAQUETE"][0] == "PAQUETE BASICO"

    def test_paquete_is_local_when_company_not_in_odoo(self, deps):
        _, df = self._paquete(deps, None)

        assert df["PAQUETE"][0] == "PAQUETE BASICO"
        assert df["_PAQUETE_LOCAL"][0] == "PAQUETE BASICO"

    def test_local_cascade_still_uses_local_package(self, deps):
        # Empresa sin paquete propio: la cascada local usa PAQUETE C 2025 aunque
        # PAQUETE muestre el nombre de la tarifa Odoo (que no existe en BD local).
        deps["company_repo"]._packages = []
        deps["package_repo"] = FakePackageRepo([
            {"id": 1, "name": "PAQUETE BASICO"},
            {"id": 9, "name": "PAQUETE C 2025"},
        ])
        deps["rates_repo"]._data[(9, 1, 1, 1, "Package")] = 7000
        uc, df = self._paquete(deps, _partner())
        assert df["PAQUETE"][0] == "GRUPO ADECCO 2026"

        result, _ = uc._assign_rates(df, uc._build_lookups())

        assert result["890201"][0] == 7000

    def test_paquete_local_column_not_in_output(self, deps):
        uc, df = self._paquete(deps, _partner())

        assert "_PAQUETE_LOCAL" not in uc._drop_internal_columns(df).columns


# ── T09: cascada Odoo (especial → base) ───────────────────────────────────

def _assign(deps, df, partner=None, lines=(), odoo=True):
    repo = FakeOdooRepo(partner_rates=[partner] if partner else [], rate_lines=list(lines)) if odoo else None
    uc = _build(deps, odoo_repo=repo)
    uc._load_odoo_rates(df)
    lookups = uc._build_lookups()
    df = uc._assign_paquete(df, lookups)
    result, colors = uc._assign_rates(df, lookups)
    return uc, result, colors


class SpyRatesRepo(FakeRatesRepo):
    def __init__(self):
        super().__init__()
        self.batch_keys = []

    def find_batch(self, keys):
        self.batch_keys.append(list(keys))
        return super().find_batch(keys)


class TestOdooCascade:
    def test_special_rate_resolves_cell_without_color(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0), _line(BASE["id"], "890201", 32200.0)]

        _, result, colors = _assign(deps, _df(), _partner(), lines)

        assert result["890201"][0] == 31100
        assert result["Total"][0] == 31100
        assert colors == {}

    def test_base_rate_used_when_special_lacks_cup(self, deps):
        lines = [_line(SPECIAL["id"], "890202", 1000.0), _line(BASE["id"], "890201", 23600.0)]

        _, result, colors = _assign(deps, _df(), _partner(), lines)

        assert result["890201"][0] == 23600
        assert colors == {}

    def test_extra_activity_uses_intra_false_line(self, deps):
        lines = [
            _line(SPECIAL["id"], "890201", 10000.0, intra=True),
            _line(SPECIAL["id"], "890201", 15000.0, intra=False),
        ]
        df = _df().with_columns(pl.lit("EXTRA").alias("TIPO DE ACTIVIDAD"))

        _, result, _ = _assign(deps, df, _partner(), lines)

        assert result["890201"][0] == 15000

    def test_odoo_resolved_cells_do_not_query_local_rates(self, deps):
        deps["rates_repo"] = SpyRatesRepo()
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]

        _assign(deps, _df(), _partner(), lines)

        assert deps["rates_repo"].batch_keys == [[]]

    def test_cell_not_in_odoo_goes_to_local_cascade(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000  # 890201, paquete propio
        lines = [_line(SPECIAL["id"], "890202", 9000.0)]

        _, result, _ = _assign(deps, _df(cups=("890201", "890202")), _partner(), lines)

        assert result["890201"][0] == 5000
        assert result["890202"][0] == 9000

    def test_company_not_in_odoo_uses_local_cascade(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000

        _, result, _ = _assign(deps, _df(), partner=None, lines=[])

        assert result["890201"][0] == 5000

    def test_odoo_unavailable_uses_local_only(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000

        uc, result, _ = _assign(deps, _df(), odoo=False)

        assert uc.odoo_available is False
        assert result["890201"][0] == 5000

    def test_odoo_never_writes(self, deps):
        odoo = FakeOdooRepo(
            partner_rates=[_partner()], rate_lines=[_line(SPECIAL["id"], "890201", 100.0)]
        )
        uc = _build(deps, odoo_repo=odoo)
        df = _df()
        uc._load_odoo_rates(df)
        lookups = uc._build_lookups()
        uc._assign_rates(uc._assign_paquete(df, lookups), lookups)

        assert odoo.write_attempts == []


# ── T10: color fase 1 local, hallazgos por fase, Leyenda y resultado ──────

PHASE1 = "fase_01_paquete_propio_local"
PHASE2 = "fase_02_paquete_c_2025"
PHASE3 = "fase_03_cualquier_paquete"
PHASE4 = "fase_04_cup_base_paquete_c"
PHASE5 = "fase_05_cup_base_cualquier_paquete"
PHASE6 = "fase_06_cualquier_ciudad"
SIN_RESOLVER = "sin_resolver"


def _local_deps(deps, *, default_package=False, extra_cups=False, extra_city=False):
    deps["provider_repo"] = FakeProviderRepo([{"id": 2, "name": "PROVEEDOR X"}])
    if default_package:
        deps["package_repo"] = FakePackageRepo([
            {"id": 1, "name": "PAQUETE BASICO"},
            {"id": 9, "name": "PAQUETE C 2025"},
        ])
    if extra_cups:
        deps["cup_repo"] = FakeCupRepo([
            {"id": 1, "code": "890201", "name": "A"},
            {"id": 2, "code": "890202", "name": "B"},
            {"id": 3, "code": "890201-1", "name": "A1"},
        ])
    if extra_city:
        deps["city_repo"] = FakeCityRepo([
            {"id": 1, "name": "BOGOTA, D.C."},
            {"id": 2, "name": "MEDELLIN"},
        ])
    return deps


def _rows(uc, key):
    return uc._findings.get(key, [])


class TestPhaseFindingsAndColors:
    def test_local_own_package_cell_is_colored_and_reported(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000
        lines = [_line(SPECIAL["id"], "890202", 9000.0)]  # Odoo no tiene 890201

        uc, result, colors = _assign(deps, _df(), _partner(), lines)

        assert colors[("890201", 0)] == "E2EFDA"
        assert _rows(uc, PHASE1) == [{
            "NIT": NIT, "Empresa": f"EMPRESA {NIT}", "Paciente": None,
            "N° Identificación": None, "Ciudad": "BOGOTA, D.C.",
            "TIPO DE ACTIVIDAD": "INTRA", "CUP": "890201",
            "Precio asignado": 5000, "Origen": "PAQUETE BASICO",
            "Fase": "Fase 1 — Paquete propio local", "Paquete original": "PAQUETE BASICO",
            "Tipo de fuente": "Paquete", "Fuente": "PAQUETE BASICO",
            "Ciudad efectiva": "BOGOTA, D.C.", "CUP efectivo": "890201",
        }]

    def test_phase2_reports_default_package(self, deps):
        # La empresa tiene paquete propio (id 1) sin precio; el respaldo es PAQUETE C 2025.
        _local_deps(deps, default_package=True)
        deps["rates_repo"]._data[(9, 1, 1, 1, "Package")] = 7000

        uc, _, colors = _assign(deps, _df(), odoo=False)

        assert colors[("890201", 0)] == "FFF2CC"
        assert [r["Origen"] for r in _rows(uc, PHASE2)] == ["PAQUETE C 2025"]

    def test_phase3_reports_source_package(self, deps):
        _local_deps(deps)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 6000

        uc, _, colors = _assign(deps, _df(), odoo=False)

        assert colors[("890201", 0)] == "F4B183"
        assert [(r["Precio asignado"], r["Origen"]) for r in _rows(uc, PHASE3)] == [(6000, "PROVEEDOR X")]

    def test_phase4_reports_base_cup_in_default_package(self, deps):
        _local_deps(deps, default_package=True, extra_cups=True)
        deps["rates_repo"]._data[(9, 1, 1, 1, "Package")] = 4000  # CUP base 890201

        uc, _, colors = _assign(deps, _df(cups=("890201-1",)), odoo=False)

        assert colors[("890201-1", 0)] == "BDD7EE"
        assert [r["Origen"] for r in _rows(uc, PHASE4)] == ["PAQUETE C 2025 (CUP 890201)"]

    def test_phase5_reports_base_cup_in_any_package(self, deps):
        _local_deps(deps, extra_cups=True)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 6500  # CUP base 890201

        uc, _, colors = _assign(deps, _df(cups=("890201-1",)), odoo=False)

        assert colors[("890201-1", 0)] == "9DC3E6"
        assert [r["Origen"] for r in _rows(uc, PHASE5)] == ["PROVEEDOR X (CUP 890201)"]

    def test_phase6_reports_any_city(self, deps):
        _local_deps(deps, extra_city=True)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 7000  # solo BOGOTA
        df = _df().with_columns(pl.lit("MEDELLIN").alias("Ciudad"))

        uc, _, colors = _assign(deps, df, odoo=False)

        assert colors[("890201", 0)] == "D5A6E6"
        assert [r["Origen"] for r in _rows(uc, PHASE6)] == ["PROVEEDOR X"]

    def test_unresolved_cells_go_to_sin_resolver(self, deps):
        uc, result, colors = _assign(deps, _df(cups=("890201", "890202")), odoo=False)

        assert colors == {}
        assert sorted(r["CUP"] for r in _rows(uc, SIN_RESOLVER)) == ["890201", "890202"]
        assert {r["Precio asignado"] for r in _rows(uc, SIN_RESOLVER)} == {1}

    def test_odoo_resolved_cells_are_not_reported(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]

        uc, _, _ = _assign(deps, _df(), _partner(), lines)

        assert all(not rows for rows in uc._findings.values())

    def test_findings_are_reset_between_runs(self, deps):
        uc, _, _ = _assign(deps, _df(), odoo=False)
        lookups = uc._build_lookups()
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000

        df = uc._assign_paquete(_df(), lookups)
        uc._assign_rates(df, lookups)

        assert not _rows(uc, SIN_RESOLVER)

    def test_company_findings_passed_with_motivo(self, deps):
        reporter = FakePhaseFindingsReporter()
        uc = _build(deps, odoo_repo=FakeOdooRepo(), findings_reporter=reporter)
        df = _df()
        uc._load_odoo_rates(df)
        lookups = uc._build_lookups()
        uc._assign_rates(uc._assign_paquete(df, lookups), lookups)

        uc._publish_findings()

        assert reporter.companies == [
            {"NIT": NIT, "Empresa": f"EMPRESA {NIT}", "Motivo": NOT_IN_ODOO}
        ]

    def test_no_findings_when_all_resolved_by_odoo(self, deps):
        reporter = FakePhaseFindingsReporter()
        odoo = FakeOdooRepo(
            partner_rates=[_partner()], rate_lines=[_line(SPECIAL["id"], "890201", 100.0)]
        )
        uc = _build(deps, odoo_repo=odoo, findings_reporter=reporter)
        df = _df()
        uc._load_odoo_rates(df)
        lookups = uc._build_lookups()
        uc._assign_rates(uc._assign_paquete(df, lookups), lookups)

        uc._publish_findings()

        assert reporter.findings == {}
        assert reporter.companies == []

    def test_result_counts_per_phase(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000
        lines = [_line(SPECIAL["id"], "890202", 9000.0)]
        reporter = FakePhaseFindingsReporter()
        deps["cup_repo"] = FakeCupRepo([
            {"id": 1, "code": "890201", "name": "A"},
            {"id": 2, "code": "890202", "name": "B"},
            {"id": 3, "code": "890203", "name": "C"},
        ])
        odoo = FakeOdooRepo(partner_rates=[_partner()], rate_lines=lines)
        uc = _build(deps, odoo_repo=odoo, findings_reporter=reporter)
        df = _df(cups=("890201", "890202", "890203"))
        uc._load_odoo_rates(df)
        lookups = uc._build_lookups()
        uc._assign_rates(uc._assign_paquete(df, lookups), lookups)

        result = uc._publish_findings()

        assert result.counts["odoo"] == 1
        assert result.counts[PHASE1] == 1
        assert result.counts[SIN_RESOLVER] == 1
        assert result.counts[PHASE2] == 0
        assert result.findings_dir == Path("fake")
        assert result.odoo_available is True
        assert reporter.odoo_available is True

    def test_legend_includes_odoo_and_six_local_phases(self, deps, tmp_path):
        import openpyxl
        import xlsxwriter

        uc = _build(deps)
        path = tmp_path / "leyenda.xlsx"
        wb = xlsxwriter.Workbook(str(path))
        uc._write_legend(wb)
        wb.close()

        ws = openpyxl.load_workbook(path)["Leyenda"]
        rows = [(ws.cell(r, 1).fill.fgColor.rgb, ws.cell(r, 2).value) for r in range(2, ws.max_row + 1)]
        assert rows[0][1] == "Sin color — Tarifa Odoo (especial/base)"
        assert [label.split(" — ")[0] for _, label in rows[1:]] == [
            "Fase 1", "Fase 2", "Fase 3", "Fase 4", "Fase 5", "Fase 6",
        ]
        assert [color[-6:] for color, _ in rows[1:]] == [
            "E2EFDA", "FFF2CC", "F4B183", "BDD7EE", "9DC3E6", "D5A6E6",
        ]


# ── T11: la opción 6 no emite user_msg ────────────────────────────────────

class UserMsgRecordingLogger:
    """Doble local: FakeLogger descarta user_msg y dejaría pasar la regresión."""

    def __init__(self):
        self.user_msgs = []

    def _log(self, message, user_msg=None):
        if user_msg:
            self.user_msgs.append(user_msg)

    def debug(self, message, *, user_msg=None):
        self._log(message, user_msg)

    def info(self, message, *, user_msg=None):
        self._log(message, user_msg)

    def warning(self, message, *, user_msg=None):
        self._log(message, user_msg)

    def error(self, message, exc_info=None, *, user_msg=None):
        self._log(message, user_msg)

    def critical(self, message, exc_info=None, *, user_msg=None):
        self._log(message, user_msg)


def _full_row(**overrides):
    base = {
        "NIT": NIT, "Empresa": "ADECCO", "Base": "GENERAL", "Ciudad": "BOGOTA, D.C.",
        "TIPO DE ACTIVIDAD": "INTRA", "Fecha Ingreso": "01/01/2020", "Empresa Misión": "",
        "Sede": "", "Medio de Pago": "", "Tipo Examen": "", "Cargo": "",
        "Paciente": "PACIENTE X", "N° Identificación": "111", "890201": 1,
    }
    base.update(overrides)
    return base


def _execute(deps, monkeypatch, tmp_path, rows, **extra):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TIAN_NIT", raising=False)
    logger = UserMsgRecordingLogger()
    uc = _build(deps, logger=logger, **extra)
    uc.execute(pl.DataFrame(rows), pl.DataFrame({"N° Identificación": [], "# FACTURA": []}))
    return logger


class TestNoUserMsg:
    def test_use_case_never_passes_user_msg_with_odoo(self, deps, monkeypatch, tmp_path):
        from tests.fakes.fake_imedical_repo import FakeImedicalRepo
        from tests.fakes.fake_tian_repo import FakeTianRepo
        from tests.fakes.fake_tian_log_generator import FakeTianLogGenerator

        odoo = FakeOdooRepo(
            partner_rates=[_partner()], rate_lines=[_line(SPECIAL["id"], "890201", 100.0)]
        )
        logger = _execute(
            deps, monkeypatch, tmp_path,
            [_full_row(), _full_row(NIT="999888777", Empresa="DESCONOCIDA")],
            odoo_repo=odoo,
            imedical_repo=FakeImedicalRepo([]),
            tian_repo=FakeTianRepo([{"nit_error": "1", "name": "X"}]),
            tian_log_generator=FakeTianLogGenerator(),
            findings_reporter=FakePhaseFindingsReporter(),
        )

        assert logger.user_msgs == []

    def test_use_case_never_passes_user_msg_when_odoo_fails(self, deps, monkeypatch, tmp_path):
        class FailingConnect(FakeOdooRepo):
            def connect(self):
                raise RuntimeError("sin red")

        logger = _execute(
            deps, monkeypatch, tmp_path, [_full_row()], odoo_repo=FailingConnect()
        )

        assert logger.user_msgs == []

    def test_use_case_never_passes_user_msg_without_base_column(self, deps, monkeypatch, tmp_path):
        from tests.fakes.fake_imedical_repo import FakeImedicalRepo

        row = _full_row()
        row.pop("Base")
        logger = _execute(
            deps, monkeypatch, tmp_path, [row], imedical_repo=FakeImedicalRepo([])
        )

        assert logger.user_msgs == []


# ── Spec 020: tarifas de Odoo vencidas ────────────────────────────────────

EXPIRED = "odoo_tarifa_vencida"
_TODAY = date(2026, 10, 20)


def _info(rate_id, name, finish, start="2025-01-01", state="approved"):
    return {
        "rate_id": rate_id, "name": name, "state": state,
        "start_date": start, "finish_date": finish,
    }


def _assign_with_info(deps, df, rate_info, lines, today=_TODAY):
    repo = FakeOdooRepo(partner_rates=[_partner()], rate_lines=list(lines), rate_info=rate_info)
    uc = _build(deps, odoo_repo=repo, today=lambda: today)
    uc._load_odoo_rates(df)
    lookups = uc._build_lookups()
    result, colors = uc._assign_rates(uc._assign_paquete(df, lookups), lookups)
    return uc, result, colors


class TestExpiredOdooRates:
    def test_expired_odoo_rate_is_assigned_and_reported(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]
        info = [_info(SPECIAL["id"], SPECIAL["name"], finish="2025-12-31")]

        uc, result, _ = _assign_with_info(deps, _df(), info, lines)

        assert result["890201"][0] == 31100
        assert _rows(uc, EXPIRED) == [{
            "NIT": NIT, "Empresa": f"EMPRESA {NIT}", "Paciente": None,
            "N° Identificación": None, "Ciudad": "BOGOTA, D.C.",
            "TIPO DE ACTIVIDAD": "INTRA", "CUP": "890201",
            "Tarifa Odoo": SPECIAL["name"], "Tipo de tarifa": "Especial",
            "Inicio vigencia": "2025-01-01", "Fin vigencia": "2025-12-31",
            "Estado Odoo": "approved", "Precio asignado": 31100,
        }]

    def test_base_rate_is_labeled_base(self, deps):
        lines = [_line(BASE["id"], "890201", 32200.0)]
        info = [_info(BASE["id"], BASE["name"], finish="2025-01-31")]

        uc, _, _ = _assign_with_info(deps, _df(), info, lines)

        assert [r["Tipo de tarifa"] for r in _rows(uc, EXPIRED)] == ["Base"]

    def test_valid_odoo_rate_is_not_reported(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]
        info = [_info(SPECIAL["id"], SPECIAL["name"], finish="2026-12-31")]

        uc, _, _ = _assign_with_info(deps, _df(), info, lines)

        assert _rows(uc, EXPIRED) == []

    def test_rate_without_finish_date_is_not_expired(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]
        info = [_info(SPECIAL["id"], SPECIAL["name"], finish=False, start=False)]

        uc, _, _ = _assign_with_info(deps, _df(), info, lines)

        assert _rows(uc, EXPIRED) == []

    def test_rate_finishing_today_is_not_expired(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]
        info = [_info(SPECIAL["id"], SPECIAL["name"], finish="2026-10-20")]

        uc, _, _ = _assign_with_info(deps, _df(), info, lines)

        assert _rows(uc, EXPIRED) == []

    def test_rate_info_failure_keeps_odoo_prices(self, deps):
        class FailingInfoRepo(FakeOdooRepo):
            def find_rate_info(self, rate_ids):
                raise RuntimeError("sin permiso")

        repo = FailingInfoRepo(
            partner_rates=[_partner()], rate_lines=[_line(SPECIAL["id"], "890201", 31100.0)]
        )
        uc = _build(deps, odoo_repo=repo, today=lambda: _TODAY)
        df = _df()
        uc._load_odoo_rates(df)
        lookups = uc._build_lookups()
        result, _ = uc._assign_rates(uc._assign_paquete(df, lookups), lookups)

        assert uc.odoo_available is True
        assert result["890201"][0] == 31100
        assert _rows(uc, EXPIRED) == []

    def test_expired_rates_are_counted_in_result(self, deps):
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]
        info = [_info(SPECIAL["id"], SPECIAL["name"], finish="2025-12-31")]

        uc, _, _ = _assign_with_info(deps, _df(), info, lines)

        assert uc._publish_findings().counts[EXPIRED] == 1


def _key(row):
    return (
        row["Fase"], row["Paquete original"], row["Ciudad"], row["CUP"],
        row["Tipo de fuente"], row["Fuente"], row["Ciudad efectiva"], row["CUP efectivo"],
    )


class TestGranularFindingKey:
    """Spec 020 RF-01/RF-02: llave original frente a fuente y valores efectivos."""

    def test_phase2_source_is_default_package(self, deps):
        _local_deps(deps, default_package=True)
        deps["rates_repo"]._data[(9, 1, 1, 1, "Package")] = 7000

        uc, _, _ = _assign(deps, _df(), odoo=False)

        assert [_key(r) for r in _rows(uc, PHASE2)] == [(
            "Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)", "PAQUETE BASICO",
            "BOGOTA, D.C.", "890201", "Paquete", "PAQUETE C 2025", "BOGOTA, D.C.", "890201",
        )]

    def test_phase3_source_type_and_name(self, deps):
        _local_deps(deps)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 6000

        uc, _, _ = _assign(deps, _df(), odoo=False)

        assert [_key(r) for r in _rows(uc, PHASE3)] == [(
            "Fase 3 — Cualquier paquete (mismo CUP, misma ciudad)", "PAQUETE BASICO",
            "BOGOTA, D.C.", "890201", "Proveedor", "PROVEEDOR X", "BOGOTA, D.C.", "890201",
        )]

    def test_phase4_effective_cup_is_base_cup(self, deps):
        _local_deps(deps, default_package=True, extra_cups=True)
        deps["rates_repo"]._data[(9, 1, 1, 1, "Package")] = 4000

        uc, _, _ = _assign(deps, _df(cups=("890201-1",)), odoo=False)

        assert [_key(r) for r in _rows(uc, PHASE4)] == [(
            "Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)", "PAQUETE BASICO",
            "BOGOTA, D.C.", "890201-1", "Paquete", "PAQUETE C 2025", "BOGOTA, D.C.", "890201",
        )]

    def test_phase5_effective_cup_is_base_cup(self, deps):
        _local_deps(deps, extra_cups=True)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 6500

        uc, _, _ = _assign(deps, _df(cups=("890201-1",)), odoo=False)

        assert [_key(r) for r in _rows(uc, PHASE5)] == [(
            "Fase 5 — Cualquier paquete (CUP base, misma ciudad)", "PAQUETE BASICO",
            "BOGOTA, D.C.", "890201-1", "Proveedor", "PROVEEDOR X", "BOGOTA, D.C.", "890201",
        )]

    def test_phase6_finding_has_effective_city(self, deps):
        _local_deps(deps, extra_city=True)
        deps["rates_repo"]._data[(2, 1, 1, 1, "Provider")] = 7000  # solo BOGOTA
        df = _df().with_columns(pl.lit("MEDELLIN").alias("Ciudad"))

        uc, _, _ = _assign(deps, df, odoo=False)

        assert [_key(r) for r in _rows(uc, PHASE6)] == [(
            "Fase 6 — Cualquier paquete/ciudad (cup + actividad)", "PAQUETE BASICO",
            "MEDELLIN", "890201", "Proveedor", "PROVEEDOR X", "BOGOTA, D.C.", "890201",
        )]

    def test_sin_resolver_has_original_key_and_no_source(self, deps):
        uc, _, _ = _assign(deps, _df(), odoo=False)

        assert [_key(r) for r in _rows(uc, SIN_RESOLVER)] == [(
            "Sin resolver", "PAQUETE BASICO", "BOGOTA, D.C.", "890201",
            None, "Sin tarifa", None, None,
        )]


# ── Bases sin tarifa: pista de alturas y sede virtual ─────────────────────

class TestBaseSinTarifa:
    @pytest.mark.parametrize("base", [
        "PISTA DE ALTURAS", "Pista de alturas", "ALTURAS NOVIEMBRE", "PISTA",
        "SEDE VIRTUAL", "virtual 1-15",
    ])
    def test_base_sin_tarifa_conserva_valores_de_entrada(self, deps, base):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000
        df = _df(nits=(NIT, NIT)).with_columns(pl.Series("Base", [base, "GENERAL"]))
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]

        uc, result, colors = _assign(deps, df, _partner(), lines)

        assert result["890201"].to_list() == [1, 31100]
        assert result["Total"].to_list() == [1, 31100]
        assert colors == {}
        assert _rows(uc, SIN_RESOLVER) == []

    def test_base_sin_tarifa_no_entra_a_fases_locales(self, deps):
        deps["rates_repo"]._data[(1, 1, 1, 1, "Package")] = 5000
        df = _df().with_columns(pl.Series("Base", ["SEDE VIRTUAL"]))

        uc, result, colors = _assign(deps, df, odoo=False)

        assert result["890201"][0] == 1
        assert colors == {}
        assert all(_rows(uc, key) == [] for key in uc._findings)

    def test_base_general_sigue_asignando_tarifa(self, deps):
        df = _df().with_columns(pl.Series("Base", ["GENERAL"]))
        lines = [_line(SPECIAL["id"], "890201", 31100.0)]

        _, result, _ = _assign(deps, df, _partner(), lines)

        assert result["890201"][0] == 31100
