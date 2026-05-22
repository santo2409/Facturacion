"""Tests para ImportRatesFromExcel use case."""
import polars as pl
import pytest
from unittest.mock import MagicMock

from src.rates.application.use_cases.import_rates_from_excel import ImportRatesFromExcel
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo
from tests.fakes.fake_city_repo import FakeCityRepo
from tests.fakes.fake_activity_repo import FakeActivityRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger


@pytest.fixture
def deps():
    return {
        "package_repo": FakePackageRepo([{"id": 1, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([{"id": 2, "name": "PROVEEDOR X"}]),
        "special_repo": FakeSpecialRepo([{"id": 3, "name": "ESPECIAL A"}]),
        "city_repo": FakeCityRepo([{"id": 1, "name": "BOGOTA"}]),
        "activities_repo": FakeActivityRepo(),
        "cup_repo": FakeCupRepo([
            {"id": 1, "code": "890201", "name": "HEMOGRAMA"},
            {"id": 2, "code": "890301", "name": "PERFIL"},
        ]),
        "fuzz": FakeFuzz(),
        "progress": FakeProgress(),
        "loader": MagicMock(),
        "mega": MagicMock(),
        "rates_repo": FakeRatesRepo(),
        "logger": FakeLogger(),
    }


def _build(deps):
    return ImportRatesFromExcel(**deps)


def test_resolve_names_exact_match(deps):
    uc = _build(deps)
    catalog = [{"name": "BOGOTA"}, {"name": "MEDELLIN"}]
    result = uc._resolve_names(["BOGOTA", "MEDELLIN"], catalog)
    assert set(result) == {"BOGOTA", "MEDELLIN"}


def test_resolve_names_deduplicates(deps):
    uc = _build(deps)
    catalog = [{"name": "BOGOTA"}]
    result = uc._resolve_names(["bogota", "BOGOTA"], catalog)
    assert len(result) == 1


def test_progress_city_saves_cities(deps):
    deps["mega"].total_dataframe = MagicMock(return_value=pl.DataFrame({
        "CIUDAD": ["BOGOTA", "MEDELLIN"],
    }))
    uc = _build(deps)
    uc._progress_city(MagicMock())
    cities = deps["city_repo"].all()
    names = [c["name"] for c in cities]
    assert "BOGOTA" in names
    assert "MEDELLIN" in names


def test_progress_packages_saves_and_creates_rates(deps):
    deps["mega"].total_dataframe = MagicMock(return_value=pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "EXAMEN": ["HEMOGRAMA"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    }))
    uc = _build(deps)
    uc._progress_packages(MagicMock())
    # Rate should be saved
    assert len(deps["rates_repo"]._data) == 1


def test_relationships_rates_skips_invalid_cup(deps):
    df = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["999999"],  # Not in cup_repo
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 0


def test_relationships_rates_strips_non_digits_from_valor(deps):
    df = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["$5.000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 1
    key = list(deps["rates_repo"]._data.keys())[0]
    assert deps["rates_repo"]._data[key] == 5000


def test_progress_providers(deps):
    deps["mega"].total_dataframe = MagicMock(return_value=pl.DataFrame({
        "CONTRATO": ["PROVEEDOR X"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "EXAMEN": ["HEMOGRAMA"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["3000"],
    }))
    uc = _build(deps)
    uc._progress_providers(MagicMock())
    assert len(deps["rates_repo"]._data) == 1


def test_progress_specials(deps):
    deps["mega"].total_dataframe = MagicMock(return_value=pl.DataFrame({
        "CONTRATO": ["ESPECIAL A"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "EXAMEN": ["HEMOGRAMA"],
        "INTRA O EXTRA": ["EXTRA"],
        "VALOR": ["7000"],
    }))
    uc = _build(deps)
    uc._progress_specials(MagicMock())
    assert len(deps["rates_repo"]._data) == 1


def test_relationships_rates_logs_invalid_cup(deps):
    df = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["999999"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 0
    assert any("CUP no encontrado" in e for e in deps["logger"].errors)


def test_relationships_rates_logs_invalid_city(deps):
    df = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["CALI"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 0
    assert any("Ciudad no encontrada" in e for e in deps["logger"].errors)


def test_relationships_rates_logs_invalid_contract(deps):
    df = pl.DataFrame({
        "CONTRATO": ["NO EXISTE"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 0
    assert any("Contrato no encontrado" in e for e in deps["logger"].errors)


def test_relationships_rates_logs_empty_valor(deps):
    df = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["N/A"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 0
    assert any("Valor vacío" in e or "valor" in e.lower() for e in deps["logger"].errors)


def test_relationships_rates_updates_existing_rate(deps):
    """Verify upsert: first insert, then update with new value."""
    df1 = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["5000"],
    })
    df2 = pl.DataFrame({
        "CONTRATO": ["PAQUETE BASICO"],
        "CIUDAD": ["BOGOTA"],
        "CUP": ["890201"],
        "INTRA O EXTRA": ["INTRA"],
        "VALOR": ["8000"],
    })
    uc = _build(deps)
    contract_all = deps["package_repo"].all()
    uc._ImportRatesFromExcel__relationships_rates(df1, contract_all, "Package")
    uc._ImportRatesFromExcel__relationships_rates(df2, contract_all, "Package")
    assert len(deps["rates_repo"]._data) == 1
    key = list(deps["rates_repo"]._data.keys())[0]
    assert deps["rates_repo"]._data[key] == 8000
