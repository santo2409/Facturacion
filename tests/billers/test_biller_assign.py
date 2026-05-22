"""Tests para la lógica de asignación de facturador."""


def biller_assign(nit, companies_all, biller_companies_all, billers_all):
    company_id = next((c["id"] for c in companies_all if c["nit"] == nit), None)
    if company_id is None:
        return "GENERAL"
    biller_id = next(
        (bc["biller"] for bc in biller_companies_all if bc["company"] == company_id), None
    )
    if biller_id is None:
        return "GENERAL"
    biller_name = next((b["name"] for b in billers_all if b["id"] == biller_id), None)
    return biller_name or "GENERAL"


COMPANIES = [
    {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
    {"id": 2, "nit": "900222222", "name": "EMPRESA B"},
    {"id": 3, "nit": "900333333", "name": "EMPRESA C"},
]
BILLERS = [{"id": 10, "name": "FACTURADOR ALFA"}, {"id": 20, "name": "FACTURADOR BETA"}]
BILLER_COMPANIES = [{"biller": 10, "company": 1}, {"biller": 20, "company": 2}]


def test_nit_con_facturador_asignado():
    assert biller_assign("900111111", COMPANIES, BILLER_COMPANIES, BILLERS) == "FACTURADOR ALFA"


def test_nit_sin_facturador():
    assert biller_assign("900333333", COMPANIES, BILLER_COMPANIES, BILLERS) == "GENERAL"


def test_nit_no_encontrado():
    assert biller_assign("999999999", COMPANIES, BILLER_COMPANIES, BILLERS) == "GENERAL"


def test_biller_id_sin_match():
    orphan = [{"biller": 99, "company": 1}]
    assert biller_assign("900111111", COMPANIES, orphan, BILLERS) == "GENERAL"


def test_nit_none():
    assert biller_assign(None, COMPANIES, BILLER_COMPANIES, BILLERS) == "GENERAL"
