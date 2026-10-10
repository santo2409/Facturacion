"""Caché de resultados de RUES desde data.json (spec 016, RF-04/RF-05): Odoo se
consulta siempre en vivo; solo lo que vino de RUES evita volver a RUES."""
import json

from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache


def _entry(nit, source="RUES/NIT", name="EMPRESA", **extra):
    return {"nit": nit, "is_company": True, "name": name, "checked_bases": "Odoo, RUES",
            "source": source, **extra}


def _write(tmp_path, entries):
    path = tmp_path / "data.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_keeps_only_entries_whose_source_starts_with_rues(tmp_path):
    path = _write(tmp_path, [
        _entry("900111111", "RUES/NIT"),
        _entry("900222222", "RUES/nombre"),
        _entry("900333333", "Odoo/NIT"),
        _entry("900444444", "BD local/NIT"),
    ])

    assert sorted(load_rues_cache(path)) == ["900111111", "900222222"]


def test_ignores_entries_without_source(tmp_path):
    legacy = {"nit": "900555555", "is_company": True, "name": "VIEJA"}  # formato anterior, sin source
    path = _write(tmp_path, [legacy, _entry("900111111")])

    assert list(load_rues_cache(path)) == ["900111111"]


def test_keys_are_normalized_nits(tmp_path):
    path = _write(tmp_path, [_entry("9001111110")])  # NIT con DV pegado

    assert list(load_rues_cache(path)) == ["900111111"]


def test_missing_or_corrupt_file_returns_empty_dict(tmp_path):
    assert load_rues_cache(tmp_path / "no_existe.json") == {}
    corrupt = tmp_path / "data.json"
    corrupt.write_text("{no es json", encoding="utf-8")
    assert load_rues_cache(corrupt) == {}


def test_entry_becomes_nit_result_with_name_and_checked_bases(tmp_path):
    path = _write(tmp_path, [_entry("900111111", name="EMPRESA UNO", nit_original="1", name_original="X")])

    result = load_rues_cache(path)["900111111"]

    assert result.name == "EMPRESA UNO"
    assert result.is_company is True
    assert result.checked_bases == "Odoo, RUES"
    assert result.source == "RUES/NIT"
    assert result.nit_original == "1" and result.name_original == "X"


def test_entries_that_are_not_companies_are_kept_as_not_found(tmp_path):
    path = _write(tmp_path, [_entry("900111111", is_company=False, name=None)])

    assert load_rues_cache(path)["900111111"].is_company is False
