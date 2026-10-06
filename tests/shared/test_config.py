"""Tests para get_paths_config() — fuente única del valor por defecto de
DIRECTORY (spec 007, RF-05/RF-07)."""

from src.shared.config import DEFAULT_DIRECTORY, get_paths_config, get_tian_config


def test_get_paths_config_usa_valor_por_defecto_cuando_directory_no_esta_definida(monkeypatch):
    monkeypatch.delenv("DIRECTORY", raising=False)

    assert get_paths_config()["directory"] == DEFAULT_DIRECTORY


def test_get_paths_config_normaliza_cadena_vacia_al_valor_por_defecto(monkeypatch):
    monkeypatch.setenv("DIRECTORY", "")

    assert get_paths_config()["directory"] == DEFAULT_DIRECTORY


def test_get_paths_config_respeta_valor_explicito(monkeypatch):
    monkeypatch.setenv("DIRECTORY", "/tmp/x")

    assert get_paths_config()["directory"] == "/tmp/x"


def test_get_tian_config_lee_env_tian_nit(monkeypatch):
    monkeypatch.setenv("TIAN_NIT", "900293402")

    assert get_tian_config()["nit"] == "900293402"


def test_get_tian_config_vacio_si_env_no_definida(monkeypatch):
    """Sin valor por defecto en código (RF-19): quien consuma la config decide abortar."""
    monkeypatch.delenv("TIAN_NIT", raising=False)

    assert get_tian_config()["nit"] == ""


def test_get_tian_config_normaliza_cadena_vacia(monkeypatch):
    monkeypatch.setenv("TIAN_NIT", "")

    assert get_tian_config()["nit"] == ""
