from src.special.domain.entities.special import Special


def test_special_creation():
    s = Special("TARIFA ESPECIAL")
    assert s.name == "TARIFA ESPECIAL"
    assert s.id is None


def test_special_with_id():
    s = Special("TARIFA ESPECIAL", id=7)
    assert s.id == 7
