from src.company.domain.entities.company import Company
from src.company.domain.entities.company_package import CompanyPackage


def test_company_creation():
    c = Company("900111111", "EMPRESA A")
    assert c.nit == "900111111"
    assert c.name == "EMPRESA A"


def test_company_equality():
    assert Company("900111111", "A") == Company("900111111", "A")
    assert Company("900111111", "A") != Company("900222222", "A")


def test_company_package_creation():
    cp = CompanyPackage(1, 10, "Package")
    assert cp.company_id == 1
    assert cp.package_id == 10
    assert cp.model == "Package"
