from src.cup.domain.entities.cup import CUP


def test_cup_creation():
    c = CUP("890201", "HEMOGRAMA")
    assert c.code == "890201"
    assert c.name == "HEMOGRAMA"


def test_cup_equality():
    assert CUP("890201", "HEMOGRAMA") == CUP("890201", "HEMOGRAMA")
    assert CUP("890201", "HEMOGRAMA") != CUP("890301", "PERFIL")
