import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from tests.fakes.fake_activity_repo import FakeActivityRepo
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_biller_repo import FakeBillerRepo
from tests.fakes.fake_city_repo import FakeCityRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo


@pytest.fixture
def fake_biller_repo():
    return FakeBillerRepo()


@pytest.fixture
def fake_company_repo():
    return FakeCompanyRepo()


@pytest.fixture
def fake_biller_company_repo():
    return FakeBillerCompanyRepo()


@pytest.fixture
def fake_cup_repo():
    return FakeCupRepo()


@pytest.fixture
def fake_rates_repo():
    return FakeRatesRepo()


@pytest.fixture
def fake_package_repo():
    return FakePackageRepo()


@pytest.fixture
def fake_provider_repo():
    return FakeProviderRepo()


@pytest.fixture
def fake_special_repo():
    return FakeSpecialRepo()


@pytest.fixture
def fake_city_repo():
    return FakeCityRepo()


@pytest.fixture
def fake_activity_repo():
    return FakeActivityRepo()


@pytest.fixture
def fake_nit_service():
    return FakeNitService()


@pytest.fixture
def fake_progress():
    return FakeProgress()


@pytest.fixture
def fake_fuzz():
    return FakeFuzz()


@pytest.fixture
def fake_logger():
    return FakeLogger()
