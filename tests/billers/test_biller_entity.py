from src.billers.domain.entities.biller import Biller


def test_biller_creation():
    b = Biller("FACTURADOR ALFA")
    assert b.name == "FACTURADOR ALFA"


def test_biller_equality():
    assert Biller("A") == Biller("A")
    assert Biller("A") != Biller("B")
