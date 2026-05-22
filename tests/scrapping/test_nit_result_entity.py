from src.scrapping.domain.entities.nit_result import NitResult


def test_nit_result_creation():
    r = NitResult(nit=900111111, is_company=True, name="EMPRESA A")
    assert r.nit == 900111111
    assert r.is_company is True
    assert r.name == "EMPRESA A"


def test_nit_result_without_name():
    r = NitResult(nit=900111111, is_company=False)
    assert r.name is None
