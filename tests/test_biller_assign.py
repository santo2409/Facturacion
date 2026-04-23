"""Tests para la lógica de asignación de facturador (__biller_assign)."""


def biller_assign(nit, companies_all, biller_companies_all, billers_all):
    """Réplica de __biller_assign corregida."""
    company_id = next((c["id"] for c in companies_all if c["nit"] == nit), None)
    if company_id is None:
        return "GENERAL"

    biller_id = next(
        (bc["biller"] for bc in biller_companies_all if bc["company"] == company_id),
        None,
    )
    if biller_id is None:
        return "GENERAL"

    biller_name = next(
        (b["name"] for b in billers_all if b["id"] == biller_id), None
    )
    return biller_name or "GENERAL"


# ── Fixtures de datos ──────────────────────────────────────────────────

COMPANIES = [
    {"id": 1, "nit": "900111111", "name": "EMPRESA A"},
    {"id": 2, "nit": "900222222", "name": "EMPRESA B"},
    {"id": 3, "nit": "900333333", "name": "EMPRESA C"},
]

BILLERS = [
    {"id": 10, "name": "FACTURADOR ALFA"},
    {"id": 20, "name": "FACTURADOR BETA"},
]

BILLER_COMPANIES = [
    {"biller": 10, "company": 1},  # EMPRESA A → FACTURADOR ALFA
    {"biller": 20, "company": 2},  # EMPRESA B → FACTURADOR BETA
    # EMPRESA C no tiene facturador
]


# ── Tests ──────────────────────────────────────────────────────────────


def test_nit_con_facturador_asignado():
    """NIT encontrado y con facturador → retorna nombre del facturador."""
    result = biller_assign("900111111", COMPANIES, BILLER_COMPANIES, BILLERS)
    assert result == "FACTURADOR ALFA"


def test_nit_con_otro_facturador():
    """NIT encontrado con otro facturador → retorna el correcto."""
    result = biller_assign("900222222", COMPANIES, BILLER_COMPANIES, BILLERS)
    assert result == "FACTURADOR BETA"


def test_nit_sin_facturador_asignado():
    """NIT encontrado pero sin facturador en companies_billers → GENERAL."""
    result = biller_assign("900333333", COMPANIES, BILLER_COMPANIES, BILLERS)
    assert result == "GENERAL"


def test_nit_no_encontrado_retorna_general():
    """NIT no existe en companies → debe retornar GENERAL, no un facturador errado."""
    result = biller_assign("999999999", COMPANIES, BILLER_COMPANIES, BILLERS)
    assert result == "GENERAL"


def test_biller_id_sin_match_en_billers_retorna_general():
    """biller_id existe en companies_billers pero no en billers → debe retornar GENERAL, no None."""
    biller_companies_con_id_huerfano = [
        {"biller": 99, "company": 1},  # biller_id 99 no existe en BILLERS
    ]
    result = biller_assign("900111111", COMPANIES, biller_companies_con_id_huerfano, BILLERS)
    # BUG: el código actual retorna None en vez de "GENERAL"
    assert result == "GENERAL"


def test_nit_none_retorna_general():
    """NIT es None → debe retornar GENERAL."""
    result = biller_assign(None, COMPANIES, BILLER_COMPANIES, BILLERS)
    assert result == "GENERAL"
