"""Tests para get_paths_config() — fuente única del valor por defecto de
DIRECTORY (spec 007, RF-05/RF-07)."""

from src.shared.config import DEFAULT_DIRECTORY, get_paths_config


def test_get_paths_config_usa_valor_por_defecto_cuando_directory_no_esta_definida(monkeypatch):
    monkeypatch.delenv("DIRECTORY", raising=False)

    assert get_paths_config()["directory"] == DEFAULT_DIRECTORY


def test_get_paths_config_normaliza_cadena_vacia_al_valor_por_defecto(monkeypatch):
    monkeypatch.setenv("DIRECTORY", "")

    assert get_paths_config()["directory"] == DEFAULT_DIRECTORY


def test_get_paths_config_respeta_valor_explicito(monkeypatch):
    monkeypatch.setenv("DIRECTORY", "/tmp/x")

    assert get_paths_config()["directory"] == "/tmp/x"
