from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from tests.fakes.fake_logger import FakeLogger


class HandlerOdooRepo(XmlRpcOdooRepository):
    """Sustituye el transporte XML-RPC delegando en un handler, sin red."""

    def __init__(self, handler):
        super().__init__("http://odoo.test", "db", "user", "key", FakeLogger(), {})
        self._handler = handler
        self.calls = []

    def _execute(self, model, method, *args, **kwargs):
        self.calls.append({"model": model, "method": method, "args": args, "kwargs": kwargs})
        return self._handler(model, method, *args, **kwargs)


def _partner(ref_num, name="EMPRESA", special=None, base=None, pid=1):
    return {
        "id": pid,
        "name": name,
        "ref_num": ref_num,
        "rate_base_special_id": special if special else False,
        "rate_base_id": base if base else False,
    }


def _domain(args):
    return args[0][0]


class TestFindPartnerRatesBatch:
    def test_exact_ref_num_match_returns_special_and_base(self):
        rows = [_partner("830050228", "ADECCO", [17534, "GRUPO ADECCO 2026"], [17235, "Tarifa basica 2025"], pid=33532)]
        repo = HandlerOdooRepo(lambda *a, **k: rows)

        result = repo.find_partner_rates_batch(["830050228"])

        assert result == [{
            "nit": "830050228",
            "partner_id": 33532,
            "name": "ADECCO",
            "special_id": 17534,
            "special_name": "GRUPO ADECCO 2026",
            "base_id": 17235,
            "base_name": "Tarifa basica 2025",
        }]
        call = repo.calls[0]
        assert call["model"] == "res.partner"
        assert _domain(call["args"]) == [["ref_num", "in", ["830050228"]]]
        assert set(call["args"][1]["fields"]) >= {"id", "name", "ref_num", "rate_base_special_id", "rate_base_id"}

    def test_partner_without_rates_returns_none_ids(self):
        repo = HandlerOdooRepo(lambda *a, **k: [_partner("900111111")])

        result = repo.find_partner_rates_batch(["900111111"])

        assert result[0]["special_id"] is None and result[0]["special_name"] is None
        assert result[0]["base_id"] is None and result[0]["base_name"] is None

    def test_ref_num_with_check_digit_matches_by_prefix(self):
        def handler(model, method, *args, **kwargs):
            domain = _domain(args)
            if domain[0][1] == "in":  # búsqueda exacta: no hay coincidencia
                return []
            return [_partner("8300502287", "ADECCO", [1, "ESP"], [2, "BASE"])]

        repo = HandlerOdooRepo(handler)

        result = repo.find_partner_rates_batch(["830050228"])

        assert [r["nit"] for r in result] == ["830050228"]
        assert result[0]["special_id"] == 1

    def test_nits_are_deduplicated_and_chunked_at_500(self):
        nits = [str(100000000 + i) for i in range(1200)]
        seen = []

        def handler(model, method, *args, **kwargs):
            chunk = _domain(args)[0][2]
            seen.append(chunk)
            return [_partner(n, pid=i) for i, n in enumerate(chunk)]

        repo = HandlerOdooRepo(handler)

        result = repo.find_partner_rates_batch(nits + nits[:10] + [""])

        assert [len(c) for c in seen] == [500, 500, 200]
        assert len(result) == 1200

    def test_chunk_error_is_skipped_and_logged(self):
        def handler(model, method, *args, **kwargs):
            raise RuntimeError("boom")

        repo = HandlerOdooRepo(handler)

        assert repo.find_partner_rates_batch(["830050228"]) == []
        assert any("boom" in w for w in repo._logger.warnings)

    def test_empty_input_makes_no_call(self):
        repo = HandlerOdooRepo(lambda *a, **k: [])

        assert repo.find_partner_rates_batch([]) == []
        assert repo.calls == []


def _line(rate=17534, city=(1807, "ACACIAS"), product=21366, intra=True, price=31100.0):
    return {
        "base_rate_id": [rate, "TARIFA"],
        "city_id": list(city) if city else False,
        "product_id": [product, "[x] NOMBRE"] if product else False,
        "intra": intra,
        "price_unit": price,
    }


def _rate_handler(lines, codes):
    def handler(model, method, *args, **kwargs):
        if model == "account.base.rate.line":
            return lines
        if model == "product.product":
            return [{"id": pid, "default_code": code} for pid, code in codes.items()]
        raise AssertionError(f"modelo inesperado: {model}")
    return handler


class TestFindRateLines:
    def test_lines_return_city_cup_intra_price(self):
        repo = HandlerOdooRepo(_rate_handler([_line()], {21366: "890262-01"}))

        result = repo.find_rate_lines([17534], ["890262-01"])

        assert result == [{
            "rate_id": 17534,
            "city": "ACACIAS",
            "cup": "890262-01",
            "intra": True,
            "price": 31100.0,
        }]
        call = repo.calls[0]
        assert call["model"] == "account.base.rate.line"
        domain = call["args"][0][0]
        assert ["base_rate_id", "in", [17534]] in domain
        assert ["product_id.default_code", "in", ["890262-01"]] in domain

    def test_default_code_is_read_in_one_product_batch(self):
        lines = [_line(product=1), _line(product=2), _line(product=1, city=(2, "AGUACHICA"))]
        repo = HandlerOdooRepo(_rate_handler(lines, {1: "890201", 2: "890202"}))

        repo.find_rate_lines([17534], ["890201", "890202"])

        product_calls = [c for c in repo.calls if c["model"] == "product.product"]
        assert len(product_calls) == 1
        assert product_calls[0]["method"] == "read"
        assert sorted(product_calls[0]["args"][0][0]) == [1, 2]

    def test_rate_ids_are_chunked_at_50(self):
        repo = HandlerOdooRepo(_rate_handler([], {}))

        repo.find_rate_lines(list(range(1, 121)) + [1, 2], ["890201"])

        line_calls = [c for c in repo.calls if c["model"] == "account.base.rate.line"]
        sizes = [len(c["args"][0][0][0][2]) for c in line_calls]
        assert sizes == [50, 50, 20]

    def test_lines_without_city_or_default_code_are_dropped(self):
        lines = [
            _line(city=None),
            _line(product=99),                # sin default_code en Odoo
            _line(product=21366, price=500.0),
        ]
        repo = HandlerOdooRepo(_rate_handler(lines, {21366: "890262-01", 99: False}))

        result = repo.find_rate_lines([17534], ["890262-01"])

        assert [r["price"] for r in result] == [500.0]

    def test_empty_inputs_make_no_call(self):
        repo = HandlerOdooRepo(_rate_handler([], {}))

        assert repo.find_rate_lines([], ["890201"]) == []
        assert repo.find_rate_lines([1], []) == []
        assert repo.calls == []


# ── spec 012 (T03): respaldo en vat para la opción 6 ──────────────────────

def _simulated(partners):
    from tests.odooInjection.test_find_clients_by_ref_num import SimulatedOdooRepo

    return SimulatedOdooRepo(partners)


def _with_rates(pid, name, *, ref_num=False, vat=False, special=None, base=None):
    return {
        "id": pid, "name": name, "ref_num": ref_num, "vat": vat,
        "rate_base_special_id": special or False, "rate_base_id": base or False,
    }


def test_partner_with_only_vat_gets_its_rates():
    repo = _simulated([
        _with_rates(7, "SOLO VAT", vat="900732772-1", special=[17534, "ESPECIAL"], base=[17235, "BASE"]),
    ])

    result = repo.find_partner_rates_batch(["900732772"])

    assert result == [{
        "nit": "900732772", "partner_id": 7, "name": "SOLO VAT",
        "special_id": 17534, "special_name": "ESPECIAL", "base_id": 17235, "base_name": "BASE",
    }]


def test_ref_num_still_wins_over_vat_for_rates():
    repo = _simulated([
        _with_rates(1, "POR REF", ref_num="900111111", base=[1, "BASE REF"]),
        _with_rates(2, "POR VAT", vat="900111111", base=[2, "BASE VAT"]),
    ])

    result = repo.find_partner_rates_batch(["900111111"])

    assert [(r["partner_id"], r["base_name"]) for r in result] == [(1, "BASE REF")]


def test_partner_found_by_ref_num_with_trailing_space_keeps_its_rates():
    repo = _simulated([_with_rates(9, "TOP DIGITAL", ref_num="900043507 ", special=[5, "ESP"])])

    assert [r["special_id"] for r in repo.find_partner_rates_batch(["900043507"])] == [5]
