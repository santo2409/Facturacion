"""Tests para SaRatesRepository con mock de Session."""
from unittest.mock import MagicMock

from src.rates.domain.entities.rate import Rate
from src.rates.infrastructure.persistence.sa_rates_repository import SaRatesRepository
from tests.fakes.fake_logger import FakeLogger


def _mock_session():
    return MagicMock()


def test_save_batch_commits():
    session = _mock_session()
    repo = SaRatesRepository(session, FakeLogger())
    rates = [Rate(1, 1, 1, 5000, 1, "Package")]
    result = repo.save_batch(rates)
    assert result == 1
    session.commit.assert_called_once()


def test_save_batch_empty():
    session = _mock_session()
    repo = SaRatesRepository(session, FakeLogger())
    assert repo.save_batch([]) == 0


def test_save_batch_rollback_on_error():
    session = _mock_session()
    session.execute.side_effect = Exception("DB error")

    repo = SaRatesRepository(session, FakeLogger())
    result = repo.save_batch([Rate(1, 1, 1, 5000, 1, "Package")])
    assert result == 0
    session.rollback.assert_called_once()


def test_find_batch_returns_dict():
    session = _mock_session()
    # Simulate query result
    row = MagicMock()
    row.__getitem__ = lambda self, i: [1, 1, 1, 5000, 1, "Package"][i]
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaRatesRepository(session, FakeLogger())
    result = repo.find_batch([(1, 1, 1, 1, "Package")])
    assert isinstance(result, dict)


def test_find_batch_empty_keys():
    session = _mock_session()
    repo = SaRatesRepository(session, FakeLogger())
    assert repo.find_batch([]) == {}


def test_find_by_name_found():
    session = _mock_session()
    row = MagicMock(rateable_id=1, city_id=1, cup_id=1, rate=5000, activity_id=1, rateable_type="Package")
    session.query.return_value.filter_by.return_value.first.return_value = row

    repo = SaRatesRepository(session, FakeLogger())
    rate = Rate(1, 1, 1, 5000, 1, "Package")
    result = repo.find_by_name(rate)
    assert result == (1, 1, 1, 5000, 1, "Package")


def test_find_by_name_not_found():
    session = _mock_session()
    session.query.return_value.filter_by.return_value.first.return_value = None

    repo = SaRatesRepository(session, FakeLogger())
    rate = Rate(1, 1, 1, 5000, 1, "Package")
    assert repo.find_by_name(rate) is None


def test_find_rate_by_cup_activity_returns_city_id():
    session = _mock_session()
    row = (10, 2, 5000, "Package", 7, 3)  # cup, activity, rate, type, rateable_id, city_id
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SaRatesRepository(session, FakeLogger())
    result = repo.find_rate_by_cup_activity([(10, 2)])

    assert result == {(10, 2): (5000, "Package", 7, 3)}
