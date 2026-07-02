import polars as pl
import pytest

from src.assign.application.use_cases.missing_rates import MissingRates
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_logger import FakeLogger


@pytest.fixture
def uc():
    return MissingRates(progress=FakeProgress(), logger=FakeLogger())


def _base_df(**cup_values):
    """Build a DataFrame with standard columns and given CUP columns."""
    data = {
        "NIT": ["900111111"],
        "Empresa": ["EMPRESA A"],
        "PAQUETE": ["PAQUETE 1"],
        "Ciudad": ["BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA"],
        "Base": ["BASE1"],
    }
    for col, val in cup_values.items():
        data[col] = [str(val)]
    return pl.DataFrame(data)


def test_extracts_records_with_value_1(uc, tmp_path):
    df = _base_df(**{"890201": "1", "100001": "5000"})
    output = tmp_path / "faltantes.xlsx"
    uc.execute(df, output)

    result = pl.read_excel(output)
    assert result.height == 1
    assert result["Examen"][0] == "890201"
    assert result["NIT"][0] == "900111111"


def test_deduplicates_by_todo(uc, tmp_path):
    df = pl.DataFrame({
        "NIT": ["900111111", "900111111"],
        "Empresa": ["EMPRESA A", "EMPRESA A"],
        "PAQUETE": ["PAQUETE 1", "PAQUETE 1"],
        "Ciudad": ["BOGOTA", "BOGOTA"],
        "TIPO DE ACTIVIDAD": ["INTRA", "INTRA"],
        "Base": ["BASE1", "BASE1"],
        "890201": ["1", "1"],
    })
    output = tmp_path / "faltantes.xlsx"
    uc.execute(df, output)

    result = pl.read_excel(output)
    assert result.height == 1


def test_empty_when_no_value_1(uc, tmp_path):
    df = _base_df(**{"890201": "5000", "100001": "3000"})
    output = tmp_path / "faltantes.xlsx"
    uc.execute(df, output)

    result = pl.read_excel(output, raise_if_empty=False)
    assert result.height == 0


def test_multiple_cups_with_value_1(uc, tmp_path):
    df = _base_df(**{"890201": "1", "100001": "1", "905727": "5000"})
    output = tmp_path / "faltantes.xlsx"
    uc.execute(df, output)

    result = pl.read_excel(output)
    assert result.height == 2
    exams = set(result["Examen"].to_list())
    assert exams == {"890201", "100001"}


def test_todo_column_not_in_output(uc, tmp_path):
    df = _base_df(**{"890201": "1"})
    output = tmp_path / "faltantes.xlsx"
    uc.execute(df, output)

    result = pl.read_excel(output)
    assert "ToDo" not in result.columns
