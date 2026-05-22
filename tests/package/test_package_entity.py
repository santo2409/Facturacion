from src.package.domain.entities.package import Package


def test_package_creation():
    p = Package("PAQUETE BASICO")
    assert p.name == "PAQUETE BASICO"
    assert p.id is None


def test_package_with_id():
    p = Package("PAQUETE BASICO", id=5)
    assert p.id == 5
