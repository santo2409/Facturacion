from src.provider.domain.entities.provider import Provider


def test_provider_creation():
    p = Provider("PROVEEDOR X")
    assert p.name == "PROVEEDOR X"
    assert p.id is None


def test_provider_with_id():
    p = Provider("PROVEEDOR X", id=3)
    assert p.id == 3
