from src.scrapping.domain.entities.nit_result import NitResult


def test_nit_result_creation():
    r = NitResult(nit=900111111, is_company=True, name="EMPRESA A")
    assert r.nit == 900111111
    assert r.is_company is True
    assert r.name == "EMPRESA A"


def test_nit_result_without_name():
    r = NitResult(nit=900111111, is_company=False)
    assert r.name is None


def test_novelty_fields_default_to_empty_or_none():
    r = NitResult(nit=900111111, is_company=True, name="EMPRESA A")

    assert r.source == ""
    assert r.nit_original is None
    assert r.name_original is None
    assert r.conflict == ""


def test_legacy_positional_construction_still_valid():
    """Los campos nuevos van al final: las construcciones existentes no se rompen."""
    r = NitResult("900111111", True, "EMPRESA A", "Odoo")

    assert r.nit == "900111111"
    assert r.checked_bases == "Odoo"
    assert r.nit_original is None


def test_novelty_fields_are_assignable():
    r = NitResult(
        nit="900111222",
        is_company=True,
        name="EMPRESA A SAS",
        checked_bases="Odoo",
        source="Odoo/nombre",
        nit_original="900111111",
        name_original="EMPRESA A",
        conflict="Nombre ya registrado en BD local con otro NIT",
    )

    assert r.source == "Odoo/nombre"
    assert r.nit_original == "900111111"
    assert r.name_original == "EMPRESA A"
    assert r.conflict


def test_dict_serialization_includes_new_fields():
    """data.json se serializa con __dict__: las claves nuevas deben viajar."""
    r = NitResult(nit="900111111", is_company=True, name="EMPRESA A", source="Odoo/NIT")

    serialized = r.__dict__

    assert serialized["source"] == "Odoo/NIT"
    assert "nit_original" in serialized
    assert "name_original" in serialized
    assert "conflict" in serialized
