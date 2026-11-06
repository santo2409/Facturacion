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


# ── AUD-68 ────────────────────────────────────────────────────────────────
import pytest  # noqa: E402

from src.shared.config import get_book_config, get_int_env  # noqa: E402


def test_get_int_env_usa_por_defecto_si_la_variable_no_existe(monkeypatch):
    monkeypatch.delenv("X_ENTERO", raising=False)
    assert get_int_env("X_ENTERO", 90) == 90


def test_get_int_env_lee_entero_valido(monkeypatch):
    monkeypatch.setenv("X_ENTERO", " 75 ")
    assert get_int_env("X_ENTERO", 90) == 75


@pytest.mark.parametrize("valor", ["", "noventa", "90.5"])
def test_get_int_env_invalido_lanza_value_error_con_el_nombre(monkeypatch, valor):
    monkeypatch.setenv("X_ENTERO", valor)
    with pytest.raises(ValueError, match="X_ENTERO"):
        get_int_env("X_ENTERO", 90)


def test_get_book_config_ausente_es_none_y_vacia_se_conserva(monkeypatch):
    monkeypatch.delenv("BOOK_ROUTE", raising=False)
    monkeypatch.setenv("BOOK_NAME", "")
    assert get_book_config() == {"route": None, "name": ""}
