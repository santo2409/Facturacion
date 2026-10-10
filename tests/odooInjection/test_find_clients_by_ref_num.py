"""Búsqueda de clientes en Odoo por ref_num con respaldo en vat (spec 012).

`SimulatedOdooRepo` evalúa los dominios sobre una lista de partners en memoria,
así los tests describen datos y no llamadas sueltas. Solo lectura: cualquier
método distinto de search_read/read hace fallar el test."""
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from tests.fakes.fake_logger import FakeLogger


def _partner(pid, name="EMPRESA", ref_num=False, vat=False):
    return {"id": pid, "name": name, "ref_num": ref_num, "vat": vat}


def _term_matches(row, term):
    field, op, value = term
    current = row.get(field)
    if op == "in":
        return current in value
    if op == "=":
        return current == value
    if op == "=like":
        return bool(current) and str(current).startswith(value.rstrip("%"))
    if op == "ilike":
        return value.lower() in str(current or "").lower()
    raise AssertionError(f"operador no soportado por el simulador: {op}")


class SimulatedOdooRepo(XmlRpcOdooRepository):
    def __init__(self, partners, fail_calls=()):
        super().__init__("http://odoo.test", "db", "user", "key", FakeLogger(), {})
        self.partners = partners
        self.fail_calls = set(fail_calls)  # índices (0-based) de llamadas que fallan
        self.calls = []

    def _execute(self, model, method, *args, **kwargs):
        index = len(self.calls)
        self.calls.append({"model": model, "method": method, "args": args, "kwargs": kwargs})
        assert method in ("search_read", "read"), f"escritura no permitida: {method}"
        if index in self.fail_calls:
            raise RuntimeError("odoo caído")
        if method == "read":
            ids = args[0][0]
            fields = args[1]["fields"]
            return [{"id": p["id"], **{f: p.get(f) for f in fields}} for p in self.partners if p["id"] in ids]
        domain = args[0][0]
        terms = [t for t in domain if isinstance(t, list)]
        use_or = "|" in domain
        rows = [
            p for p in self.partners
            if (any if use_or else all)(_term_matches(p, t) for t in terms)
        ]
        options = args[1] if len(args) > 1 else kwargs
        fields = options["fields"]
        ordered = sorted(rows, key=lambda r: r["id"])[: options.get("limit") or None]
        return [{"id": p["id"], **{f: p.get(f) for f in fields}} for p in ordered]

    def stages(self):
        """[(campo, operador, cantidad de NIT consultados)] en el orden de las llamadas."""
        result = []
        for call in self.calls:
            domain = call["args"][0][0]
            terms = [t for t in domain if isinstance(t, list)]
            field, op, _ = terms[0]
            size = len(terms[0][2]) if op == "in" else len(terms)
            result.append((field, op, size))
        return result


def _find(partners, nits, **kwargs):
    repo = SimulatedOdooRepo(partners, **kwargs)
    found = repo._find_partners_by_document(nits, ["id", "name"])
    return repo, found


# ── T01: helper de 4 etapas ───────────────────────────────────────────────

def test_ref_num_exact_stage_wins_over_vat():
    partners = [_partner(1, ref_num="900111111"), _partner(2, vat="900111111")]

    repo, found = _find(partners, ["900111111"])

    assert found["900111111"]["id"] == 1
    assert repo.stages() == [("ref_num", "in", 1)]  # no consultó vat


def test_ref_num_like_stage_finds_trailing_space_and_pasted_check_digit():
    partners = [_partner(1, ref_num="900043507 "), _partner(2, ref_num="9002048797")]

    repo, found = _find(partners, ["900043507", "900204879"])

    assert {nit: row["id"] for nit, row in found.items()} == {"900043507": 1, "900204879": 2}
    assert [s[:2] for s in repo.stages()] == [("ref_num", "in"), ("ref_num", "=like")]


def test_vat_exact_stage_for_partner_without_ref_num():
    repo, found = _find([_partner(1, vat="900732772")], ["900732772"])

    assert found["900732772"]["id"] == 1
    assert [s[:2] for s in repo.stages()] == [("ref_num", "in"), ("ref_num", "=like"), ("vat", "in")]


def test_vat_like_stage_for_vat_with_check_digit():
    repo, found = _find([_partner(1, vat="900732772-1")], ["900732772"])

    assert found["900732772"]["id"] == 1
    assert repo.stages()[-1][:2] == ("vat", "=like")


def test_each_stage_only_queries_pending_nits():
    partners = [_partner(1, ref_num="900111111"), _partner(2, vat="900732772")]

    repo, found = _find(partners, ["900111111", "900732772"])

    assert set(found) == {"900111111", "900732772"}
    assert repo.stages() == [
        ("ref_num", "in", 2),     # los dos NIT
        ("ref_num", "=like", 1),  # solo el pendiente
        ("vat", "in", 1),         # solo el pendiente
    ]


def test_in_stages_are_chunked_at_500_and_like_stages_at_50():
    nits = [str(100000000 + i) for i in range(120)]

    repo, found = _find([], nits)  # nada existe: recorre las 4 etapas completas

    assert found == {}
    assert repo.stages() == [
        ("ref_num", "in", 120),
        ("ref_num", "=like", 50), ("ref_num", "=like", 50), ("ref_num", "=like", 20),
        ("vat", "in", 120),
        ("vat", "=like", 50), ("vat", "=like", 50), ("vat", "=like", 20),
    ]


def test_exact_stage_is_chunked_at_500_and_stops_when_everything_is_found():
    nits = [str(100000000 + i) for i in range(1200)]
    partners = [_partner(i + 1, ref_num=n) for i, n in enumerate(nits)]

    repo, found = _find(partners + [], nits + nits[:10] + [""])

    assert len(found) == 1200
    assert repo.stages() == [("ref_num", "in", 500), ("ref_num", "in", 500), ("ref_num", "in", 200)]


def test_candidate_is_rejected_when_normalized_document_differs():
    # un NIT de 9 dígitos que empieza igual que el documento buscado (8 dígitos) no es el mismo
    partners = [_partner(1, ref_num="900111110")]

    _, found = _find(partners, ["90011111"])

    assert found == {}


def test_stage_failure_is_logged_and_next_stage_runs():
    partners = [_partner(1, ref_num="900111111")]

    repo, found = _find(partners, ["900111111"], fail_calls={0})  # falla la etapa ref_num exacta

    assert found["900111111"]["id"] == 1  # la etapa ref_num =like lo encuentra
    assert any("odoo caído" in w for w in repo._logger.warnings)


def test_every_call_is_a_read():
    partners = [_partner(1, vat="900732772-1")]

    repo, _ = _find(partners, ["900732772", "999999999"])

    assert repo.calls and all(c["model"] == "res.partner" and c["method"] == "search_read" for c in repo.calls)


def test_empty_input_makes_no_call():
    repo, found = _find([_partner(1, ref_num="1")], ["", None])

    assert found == {} and repo.calls == []


# ── T01: documento devuelto ───────────────────────────────────────────────

def test_document_of_prefers_ref_num():
    assert XmlRpcOdooRepository._document_of({"ref_num": "830050228 ", "vat": "999"}) == "830050228"


def test_document_of_falls_back_to_vat_without_check_digit():
    assert XmlRpcOdooRepository._document_of({"ref_num": False, "vat": "900732772-1"}) == "900732772"


def test_document_of_is_empty_without_any_document():
    assert XmlRpcOdooRepository._document_of({"ref_num": False, "vat": False}) == ""


# ── T02: find_client y find_clients_batch ─────────────────────────────────

def test_find_client_by_ref_num_without_vat():
    repo = SimulatedOdooRepo([_partner(33532, "ADECCO SERVICIOS", ref_num="830050228")])

    assert repo.find_client("830050228", "ADECCO") == (33532, "ADECCO SERVICIOS", "NIT")


def test_find_client_only_vat():
    repo = SimulatedOdooRepo([_partner(7, "EMPRESA NUEVA", vat="900732772")])

    assert repo.find_client("900732772", "X") == (7, "EMPRESA NUEVA", "NIT")


def test_find_client_vat_with_check_digit():
    repo = SimulatedOdooRepo([_partner(7, "EMPRESA NUEVA", vat="900732772-1")])

    assert repo.find_client("900732772", "X") == (7, "EMPRESA NUEVA", "NIT")


def test_find_client_ref_num_with_trailing_space():
    repo = SimulatedOdooRepo([_partner(9, "TOP DIGITAL", ref_num="900043507 ")])

    assert repo.find_client("900043507", "X") == (9, "TOP DIGITAL", "NIT")


def test_find_client_returns_none_triplet_when_missing():
    repo = SimulatedOdooRepo([_partner(1, ref_num="111111111")])

    assert repo.find_client("999999999", "X") == (None, None, None)


def test_find_client_prefers_ref_num_over_vat_owner():
    repo = SimulatedOdooRepo([_partner(1, "POR REF", ref_num="900111111"), _partner(2, "POR VAT", vat="900111111")])

    assert repo.find_client("900111111", "X") == (1, "POR REF", "NIT")
    assert repo.stages() == [("ref_num", "in", 1)]


def test_find_clients_batch_mixed_1200_nits():
    nits = [str(100000000 + i) for i in range(1200)]
    partners = [_partner(i + 1, f"E{i}", ref_num=n) for i, n in enumerate(nits[:1198])]
    partners.append(_partner(5000, "SOLO VAT", vat=nits[1198]))
    partners.append(_partner(5001, "VAT CON DV", vat=f"{nits[1199]}-3"))
    repo = SimulatedOdooRepo(partners)

    found = repo.find_clients_batch(nits)

    assert len(found) == 1200
    assert found[nits[0]] == (1, "E0", "NIT")
    assert found[nits[1198]] == (5000, "SOLO VAT", "NIT")
    assert found[nits[1199]] == (5001, "VAT CON DV", "NIT")
    stages = repo.stages()
    assert stages[:3] == [("ref_num", "in", 500), ("ref_num", "in", 500), ("ref_num", "in", 200)]
    # solo los 2 pendientes siguen en las etapas siguientes
    assert ("ref_num", "=like", 2) in stages and ("vat", "in", 2) in stages
    assert max(s[2] for s in stages[3:]) == 2


def test_find_clients_batch_keeps_return_format_and_ignores_empty():
    repo = SimulatedOdooRepo([_partner(1, "A", ref_num="900111111")])

    assert repo.find_clients_batch(["900111111", "", "900111111"]) == {"900111111": (1, "A", "NIT")}
    assert repo.find_clients_batch([]) == {}


# ── T04: documento devuelto por find_clients_by_name y get_nit ────────────

def test_find_clients_by_name_returns_ref_num_document():
    repo = SimulatedOdooRepo([_partner(1, "ADECCO SERVICIOS", ref_num="830050228")])

    assert repo.find_clients_by_name("ADECCO SERVICIOS") == [
        {"id": 1, "name": "ADECCO SERVICIOS", "vat": "830050228"}
    ]


def test_find_clients_by_name_falls_back_to_vat():
    repo = SimulatedOdooRepo([_partner(2, "EMPRESA NUEVA", vat="900732772-1")])

    assert repo.find_clients_by_name("EMPRESA NUEVA")[0]["vat"] == "900732772"


def test_find_clients_by_name_requests_ref_num_and_vat_and_respects_limit():
    repo = SimulatedOdooRepo([_partner(i, f"EMPRESA {i}", ref_num=str(900000000 + i)) for i in range(1, 6)])

    result = repo.find_clients_by_name("EMPRESA", limit=3)

    assert len(result) == 3
    assert repo.calls[0]["args"][1]["fields"] == ["id", "name", "ref_num", "vat"]


def test_get_nit_prefers_ref_num():
    repo = SimulatedOdooRepo([_partner(1, ref_num="830050228 ", vat="999999999")])

    assert repo.get_nit(1) == "830050228"


def test_get_nit_falls_back_to_vat_without_check_digit():
    repo = SimulatedOdooRepo([_partner(2, vat="900732772-1")])

    assert repo.get_nit(2) == "900732772"


def test_get_nit_returns_none_without_document():
    repo = SimulatedOdooRepo([_partner(3)])

    assert repo.get_nit(3) is None
    assert repo.get_nit(999) is None
