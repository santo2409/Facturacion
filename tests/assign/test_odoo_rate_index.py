from datetime import date

from src.assign.domain.odoo_rate_index import OdooRateIndex


def _line(rate_id=1, city="BOGOTA, D.C.", cup="890201", intra=True, price=10000):
    return {"rate_id": rate_id, "city": city, "cup": cup, "intra": intra, "price": price}


class TestOdooRateIndex:
    def test_price_returns_intra_line_for_intra_activity(self):
        index = OdooRateIndex([_line(price=31100)])
        assert index.price(1, "BOGOTA, D.C.", "890201", "INTRA") == 31100

    def test_extra_activity_uses_intra_false(self):
        index = OdooRateIndex([
            _line(intra=True, price=10000),
            _line(intra=False, price=15000),
        ])
        assert index.price(1, "BOGOTA, D.C.", "890201", "EXTRA") == 15000

    def test_city_match_ignores_accents_case_and_spaces(self):
        index = OdooRateIndex([_line(city="MEDELLÍN", price=9000)])
        assert index.price(1, "  medellin ", "890201", "INTRA") == 9000

    def test_returns_none_when_rate_id_is_none(self):
        index = OdooRateIndex([_line()])
        assert index.price(None, "BOGOTA, D.C.", "890201", "INTRA") is None

    def test_ignores_non_positive_prices(self):
        index = OdooRateIndex([_line(price=0), _line(cup="890202", price=-5)])
        assert index.price(1, "BOGOTA, D.C.", "890201", "INTRA") is None
        assert index.price(1, "BOGOTA, D.C.", "890202", "INTRA") is None

    def test_first_line_wins_on_duplicate_key(self):
        index = OdooRateIndex([_line(price=100), _line(price=200)])
        assert index.price(1, "BOGOTA, D.C.", "890201", "INTRA") == 100

    def test_unknown_activity_returns_none(self):
        index = OdooRateIndex([_line()])
        assert index.price(1, "BOGOTA, D.C.", "890201", "OTRA") is None
        assert index.price(1, "BOGOTA, D.C.", "890201", None) is None

    def test_rate_id_is_part_of_the_key(self):
        index = OdooRateIndex([_line(rate_id=1, price=100), _line(rate_id=2, price=200)])
        assert index.price(2, "BOGOTA, D.C.", "890201", "INTRA") == 200


class TestOdooRateIndexLookup:
    def test_lookup_returns_rate_id_name_and_validity(self):
        info = [{
            "rate_id": 7, "name": "TARIFA ENEL 2025", "state": "approved",
            "start_date": "2025-01-01", "finish_date": "2025-12-31",
        }]
        index = OdooRateIndex([_line(rate_id=7, price=31100)], rates_info=info)

        hit = index.lookup(7, "BOGOTA, D.C.", "890201", "INTRA")

        assert hit.price == 31100
        assert hit.rate_id == 7
        assert hit.rate_name == "TARIFA ENEL 2025"
        assert hit.start_date == date(2025, 1, 1)
        assert hit.finish_date == date(2025, 12, 31)
        assert hit.state == "approved"

    def test_lookup_without_rate_info_has_no_validity(self):
        index = OdooRateIndex([_line(rate_id=7)])

        hit = index.lookup(7, "BOGOTA, D.C.", "890201", "INTRA")

        assert hit.price == 10000
        assert hit.rate_name is None
        assert hit.state is None
        assert hit.finish_date is None

    def test_odoo_false_dates_become_none(self):
        info = [{"rate_id": 1, "name": "X", "state": False, "start_date": False, "finish_date": False}]
        index = OdooRateIndex([_line()], rates_info=info)

        hit = index.lookup(1, "BOGOTA, D.C.", "890201", "INTRA")

        assert hit.start_date is None
        assert hit.finish_date is None

    def test_lookup_returns_none_when_missing(self):
        index = OdooRateIndex([_line()])
        assert index.lookup(1, "BOGOTA, D.C.", "999999", "INTRA") is None
        assert index.lookup(None, "BOGOTA, D.C.", "890201", "INTRA") is None
