from src.rates.domain.entities.rate import Rate


def test_rate_creation():
    r = Rate(rateable_id=1, city_id=2, cup_id=3, rate=5000, activity_id=1, rateable_type="Package")
    assert r.rateable_id == 1
    assert r.city_id == 2
    assert r.cup_id == 3
    assert r.rate == 5000
    assert r.activity_id == 1
    assert r.rateable_type == "Package"


def test_rate_equality():
    r1 = Rate(1, 2, 3, 5000, 1, "Package")
    r2 = Rate(1, 2, 3, 5000, 1, "Package")
    assert r1 == r2


def test_rate_different_values():
    r1 = Rate(1, 2, 3, 5000, 1, "Package")
    r2 = Rate(1, 2, 3, 6000, 1, "Package")
    assert r1 != r2
