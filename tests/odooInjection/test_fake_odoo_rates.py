from tests.fakes.fake_odoo_repo import FakeOdooRepo
from tests.odooInjection.test_odoo_partner_rates import HandlerOdooRepo

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


def test_existing_fake_behavior_unchanged():
    repo = FakeOdooRepo(clients={"900": {"id": 7, "name": "EMPRESA"}})

    assert repo.find_client("900", "EMPRESA") == (7, "EMPRESA", "NIT")
    assert repo.find_partner_rates_batch(["900"]) == []
    assert repo.find_rate_lines([], []) == []
    assert repo.write_attempts == []


_INFO = {
    "rate_id": 10, "name": "TARIFA 2025", "state": "approved",
    "start_date": "2025-01-01", "finish_date": "2025-12-31",
}


def test_fake_filters_rate_info_by_rate_ids():
    repo = FakeOdooRepo(rate_info=[_INFO, {**_INFO, "rate_id": 20}])

    assert repo.find_rate_info([10, 99]) == [_INFO]
    assert repo.calls["find_rate_info"] == 1


def test_find_rate_info_returns_validity_fields():
    rows = [{
        "id": 10, "name": "TARIFA 2025", "state": "approved",
        "start_date": "2025-01-01", "finish_date": "2025-12-31",
    }]
    repo = HandlerOdooRepo(lambda *a, **k: rows)

    result = repo.find_rate_info([10, 10, 0])

    assert result == [_INFO]
    call = repo.calls[0]
    assert (call["model"], call["method"]) == ("account.base.rate", "search_read")
    assert call["args"][0] == [[["id", "in", [10]]]]
    assert call["args"][1]["fields"] ==["name", "state", "start_date", "finish_date"]


def test_find_rate_info_batches_requests_and_skips_empty():
    repo = HandlerOdooRepo(lambda *a, **k: [])

    assert repo.find_rate_info([]) == []
    assert repo.calls == []
    repo.find_rate_info(list(range(1, 121)))
    assert len(repo.calls) == 3  # lotes de 50
