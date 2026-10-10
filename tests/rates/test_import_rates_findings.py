"""Hallazgos por tipo de la opción 4 en libros por ejecución (spec 011, RF-04/RF-07/RF-08)."""
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from src.rates.application.use_cases.import_rates_from_excel import (
    RATE_FINDING_COLUMNS,
    ImportRatesFromExcel,
)
from tests.fakes.fake_activity_repo import FakeActivityRepo
from tests.fakes.fake_city_repo import FakeCityRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_findings_writer import FakeFindingsWriter
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo

CONTRACTS = [{"id": 1, "name": "PAQUETE BASICO"}]


class RecordingLogger:
    """Doble local que registra `user_msg` (FakeLogger lo descarta)."""

    def __init__(self):
        self.errors = []
        self.user_msgs = []

    def _rec(self, user_msg):
        if user_msg:
            self.user_msgs.append(user_msg)

    def info(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def warning(self, msg, *, user_msg=None, **_):
        self._rec(user_msg)

    def error(self, msg, *, user_msg=None, **_):
        self.errors.append(msg)
        self._rec(user_msg)


@pytest.fixture
def deps():
    return {
        "package_repo": FakePackageRepo(CONTRACTS),
        "provider_repo": FakeProviderRepo([]),
        "special_repo": FakeSpecialRepo([]),
        "city_repo": FakeCityRepo([{"id": 1, "name": "BOGOTA"}]),
        "activities_repo": FakeActivityRepo(),
        "cup_repo": FakeCupRepo([{"id": 1, "code": "890201", "name": "HEMOGRAMA"}]),
        "fuzz": FakeFuzz(),
        "progress": FakeProgress(),
        "loader": MagicMock(),
        "mega": MagicMock(),
        "rates_repo": FakeRatesRepo(),
        "logger": RecordingLogger(),
        "findings_writer": FakeFindingsWriter(),
    }


def _row(contract="PAQUETE BASICO", city="BOGOTA", cup="890201", activity="INTRA",
         valor="5000", hoja="Paquetes", fila=2):
    return {"CONTRATO": contract, "CIUDAD": city, "CUP": cup, "INTRA O EXTRA": activity,
            "VALOR": valor, "_HOJA": hoja, "_FILA": fila}


def _run(deps, rows):
    uc = ImportRatesFromExcel(**deps)
    df = pl.DataFrame(rows, schema_overrides={"_FILA": pl.Int64})
    uc._ImportRatesFromExcel__relationships_rates(df, CONTRACTS, "Package")
    return uc


def _finding(contract="PAQUETE BASICO", city="BOGOTA", cup="890201", activity="INTRA",
             valor="5000", hoja="Paquetes", fila=2):
    return {"Hoja": hoja, "Fila": fila, "CONTRATO": contract, "CIUDAD": city, "CUP": cup,
            "INTRA O EXTRA": activity, "VALOR": valor}


def test_each_rejected_row_lands_in_its_finding_book(deps):
    uc = _run(deps, [
        _row(contract="NO EXISTE", fila=3),
        _row(city="NARNIA", fila=5),
        _row(valor="", hoja="TarifasEspeciales2", fila=2),
    ])

    assert uc._findings["contrato_no_existe"] == [_finding(contract="NO EXISTE", fila=3)]
    assert uc._findings["ciudad_no_existe"] == [_finding(city="NARNIA", fila=5)]
    assert uc._findings["tarifa_vacia"] == [_finding(valor="", hoja="TarifasEspeciales2", fila=2)]


def test_cup_and_activity_findings(deps):
    uc = _run(deps, [_row(cup="999999", fila=4), _row(activity="XYZ", fila=6)])

    assert uc._findings["cup_no_existe"] == [_finding(cup="999999", fila=4)]
    assert uc._findings["actividad_invalida"] == [_finding(activity="XYZ", fila=6)]


def test_valid_rows_are_still_saved(deps):
    _run(deps, [_row(contract="NO EXISTE", fila=3), _row(fila=4)])

    assert list(deps["rates_repo"]._data.values()) == [5000]


def test_original_valor_is_reported_not_the_cleaned_one(deps):
    uc = _run(deps, [_row(valor="abc", fila=7)])

    assert uc._findings["tarifa_vacia"] == [_finding(valor="abc", fila=7)]


def test_rows_without_origin_columns_use_none(deps):
    row = {k: v for k, v in _row(contract="NO EXISTE").items() if not k.startswith("_")}

    uc = _run(deps, [row])

    assert uc._findings["contrato_no_existe"] == [_finding(contract="NO EXISTE", hoja=None, fila=None)]


def test_same_row_failing_in_two_passes_is_reported_once(deps):
    uc = ImportRatesFromExcel(**deps)
    df = pl.DataFrame([_row(contract="NO EXISTE", fila=3)], schema_overrides={"_FILA": pl.Int64})

    uc._ImportRatesFromExcel__relationships_rates(df, CONTRACTS, "Package")
    uc._ImportRatesFromExcel__relationships_rates(df, CONTRACTS, "Provider")

    assert len(uc._findings["contrato_no_existe"]) == 1


def test_no_per_row_user_msg(deps):
    _run(deps, [_row(contract="NO EXISTE", fila=3), _row(city="NARNIA", fila=5), _row(valor="", fila=6)])

    assert deps["logger"].user_msgs == []
    assert len(deps["logger"].errors) == 3  # el detalle técnico por fila se conserva


def test_single_summary_user_msg_with_counts_and_folder(deps):
    uc = _run(deps, [_row(contract="NO EXISTE", fila=3), _row(valor="", fila=6), _row(valor="", fila=7)])

    uc._publish_findings()

    assert len(deps["logger"].user_msgs) == 1
    summary = deps["logger"].user_msgs[0]
    assert "contrato_no_existe=1" in summary and "tarifa_vacia=2" in summary
    assert "fake" in summary  # ruta de la carpeta que devolvió el writer
    assert deps["findings_writer"].columns == RATE_FINDING_COLUMNS


def test_no_findings_no_folder_and_summary_says_sin_hallazgos(deps):
    uc = _run(deps, [_row(fila=2), _row(fila=3)])

    uc._publish_findings()

    assert deps["findings_writer"].books == {}
    assert deps["logger"].user_msgs == ["Sin hallazgos."]


def test_summary_without_writer_still_reports_counts(deps):
    deps["findings_writer"] = None
    uc = _run(deps, [_row(contract="NO EXISTE", fila=3)])

    uc._publish_findings()

    assert deps["logger"].user_msgs == ["Hallazgos: contrato_no_existe=1."]


def test_execute_resets_findings_and_publishes_once(deps):
    frames = {
        "Ciudades": pl.DataFrame({"CIUDAD": ["BOGOTA"]}),
        "Paquetes": pl.DataFrame([_row(contract="PAQUETE BASICO", city="NARNIA", fila=2)],
                                 schema_overrides={"_FILA": pl.Int64}),
        "Proveedores": pl.DataFrame({k: [] for k in _row()}, schema={k: pl.Utf8 for k in _row()}),
        "TarifasEspeciales": pl.DataFrame({k: [] for k in _row()}, schema={k: pl.Utf8 for k in _row()}),
    }
    deps["mega"].total_dataframe = MagicMock(side_effect=lambda loader, excel, cb: frames[cb])
    uc = ImportRatesFromExcel(**deps)
    uc._findings["tarifa_vacia"].append({"stale": True})  # resto de una corrida anterior

    uc.execute(excel=MagicMock())

    assert "tarifa_vacia" in uc._findings and uc._findings["tarifa_vacia"] == []
    assert len(uc._findings["ciudad_no_existe"]) == 1
    assert deps["findings_writer"].books == {"ciudad_no_existe": uc._findings["ciudad_no_existe"]}
    assert sum("ciudad_no_existe=1" in m for m in deps["logger"].user_msgs) == 1
