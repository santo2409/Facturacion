from src.company.domain.entities.company import Company


def test_company_creation():
    c = Company("900111111", "EMPRESA A")
    assert c.nit == "900111111"
    assert c.name == "EMPRESA A"


def test_company_equality():
    assert Company("900111111", "A") == Company("900111111", "A")
    assert Company("900111111", "A") != Company("900222222", "A")


def test_company_normalizes_int_nit_to_str():
    c = Company(900111111, "EMPRESA A")
    assert c.nit == "900111111"
    assert isinstance(c.nit, str)


def test_company_preserves_none_nit():
    c = Company(None, "EMPRESA A")
    assert c.nit is None

