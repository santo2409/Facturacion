from src.city.domain.entities.city import City


def test_city_creation():
    c = City("BOGOTA")
    assert c.name == "BOGOTA"


def test_city_equality():
    assert City("BOGOTA") == City("BOGOTA")
    assert City("BOGOTA") != City("MEDELLIN")
