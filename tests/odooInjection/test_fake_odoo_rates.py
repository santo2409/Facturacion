from tests.fakes.fake_odoo_repo import FakeOdooRepo

_PARTNER = {
    "nit": "830050228", "partner_id": 1, "name": "ADECCO",
    "special_id": 10, "special_name": "ESPECIAL", "base_id": 20, "base_name": "BASE",
}


def _line(rate_id, cup, price=100, city="BOGOTA, D.C.", intra=True):
    return {"rate_id": rate_id, "city": city, "cup": cup, "intra": intra, "price": price}


def test_fake_filters_partners_by_nit():
    repo = FakeOdooRepo(partner_rates=[_PARTNER, {**_PARTNER, "nit": "900111111"}])

    assert repo.find_partner_rates_batch(["830050228", "000"]) == [_PARTNER]


def test_fake_filters_lines_by_rate_ids_and_cups():
    lines = [_line(10, "890201"), _line(10, "890202"), _line(20, "890201"), _line(30, "890201")]
    repo = FakeOdooRepo(rate_lines=lines)

    result = repo.find_rate_lines([10, 20], ["890201"])

    assert result == [lines[0], lines[2]]


def test_fake_counts_calls():
    repo = FakeOdooRepo()

    repo.find_partner_rates_batch(["1"])
    repo.find_partner_rates_batch(["2"])
    repo.find_rate_lines([1], ["x"])

    assert repo.calls == {"find_partner_rates_batch": 2, "find_rate_lines": 1}


def test_fake_records_write_attempts():
    repo = FakeOdooRepo()

    repo.create_client("1", "A")
    repo.create_invoice({"x": 1})

    assert repo.write_attempts == ["create_client", "create_invoice"]


def test_existing_fake_behavior_unchanged():
    repo = FakeOdooRepo(clients={"900": {"id": 7, "name": "EMPRESA"}})

    assert repo.find_client("900", "EMPRESA") == (7, "EMPRESA", "NIT")
    assert repo.find_partner_rates_batch(["900"]) == []
    assert repo.find_rate_lines([], []) == []
    assert repo.write_attempts == []
