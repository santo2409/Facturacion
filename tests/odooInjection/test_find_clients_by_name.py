from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_odoo_repo import FakeOdooRepo


class StubExecuteOdooRepo(XmlRpcOdooRepository):
    """Sustituye el transporte XML-RPC registrando las llamadas, sin red."""

    def __init__(self, rows):
        super().__init__("http://odoo.test", "db", "user", "key", FakeLogger(), {})
        self._rows = rows
        self.calls = []

    def _execute(self, model, method, *args, **kwargs):
        self.calls.append({"model": model, "method": method, "args": args, "kwargs": kwargs})
        return self._rows


def test_find_clients_by_name_returns_list_of_dicts():
    repo = StubExecuteOdooRepo(
        [{"id": 7, "name": "EMPRESA A SAS", "vat": "900111111"}]
    )

    result = repo.find_clients_by_name("EMPRESA A SAS")

    assert result == [{"id": 7, "name": "EMPRESA A SAS", "vat": "900111111"}]


def test_requests_id_name_ref_num_and_vat_fields():
    # spec 012: el documento sale de ref_num y, si falta, de vat
    repo = StubExecuteOdooRepo([])

    repo.find_clients_by_name("EMPRESA A")

    assert repo.calls[0]["model"] == "res.partner"
    assert repo.calls[0]["args"][1]["fields"] == ["id", "name", "ref_num", "vat"]


def test_strips_corporate_suffix_from_search_term():
    repo = StubExecuteOdooRepo([])

    repo.find_clients_by_name("EMPRESA A SAS")

    condition = repo.calls[0]["args"][0][0][0]
    assert condition == ["name", "ilike", "EMPRESA A"]


def test_keeps_original_name_when_stripping_leaves_nothing():
    repo = StubExecuteOdooRepo([])

    repo.find_clients_by_name("SAS")

    condition = repo.calls[0]["args"][0][0][0]
    assert condition[2] == "SAS"


def test_vat_is_normalized_without_verification_digit():
    repo = StubExecuteOdooRepo(
        [{"id": 1, "name": "EMPRESA A", "vat": "900123456-7"}]
    )

    result = repo.find_clients_by_name("EMPRESA A")

    assert result[0]["vat"] == "900123456"


def test_missing_vat_becomes_empty_string():
    repo = StubExecuteOdooRepo([{"id": 1, "name": "EMPRESA A", "vat": False}])

    result = repo.find_clients_by_name("EMPRESA A")

    assert result[0]["vat"] == ""


def test_respects_limit():
    repo = StubExecuteOdooRepo([])

    repo.find_clients_by_name("EMPRESA A", limit=3)

    assert repo.calls[0]["args"][1]["limit"] == 3


def test_returns_empty_list_when_no_rows():
    repo = StubExecuteOdooRepo([])

    assert repo.find_clients_by_name("EMPRESA A") == []


def test_find_client_by_name_still_works():
    """No regresión: assigned_rates sigue usando el método original."""
    repo = StubExecuteOdooRepo([{"id": 9, "name": "EMPRESA A SAS"}])

    assert repo.find_client_by_name("EMPRESA A SAS") == (9, "EMPRESA A SAS", "nombre")


def test_fake_returns_list_of_dicts_with_id_name_vat():
    repo = FakeOdooRepo(clients={"900111111": {"id": 1, "name": "EMPRESA A SAS"}})

    result = repo.find_clients_by_name("EMPRESA A SAS")

    assert result == [{"id": 1, "name": "EMPRESA A SAS", "vat": "900111111"}]


def test_fake_respects_limit():
    repo = FakeOdooRepo(
        clients={
            "900111111": {"id": 1, "name": "EMPRESA A"},
            "900222222": {"id": 2, "name": "EMPRESA A"},
        }
    )

    assert len(repo.find_clients_by_name("EMPRESA A", limit=1)) == 1


def test_fake_returns_empty_when_no_match():
    repo = FakeOdooRepo(clients={"900111111": {"id": 1, "name": "EMPRESA A"}})

    assert repo.find_clients_by_name("OTRA COSA") == []
