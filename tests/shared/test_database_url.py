"""AUD-45: una sola regla de URL de BD para la app y Alembic (credenciales ficticias)."""

import pytest
from alembic.config import Config

from src.shared.database.database import build_database_url, database_connect_args

_VARS = ("DATABASE_URL", "SUPABASE_DB_USER", "SUPABASE_DB_PASSWORD", "SUPABASE_DB_HOST",
         "SUPABASE_DB_PORT", "SUPABASE_DB_NAME", "DB_CONNECT_TIMEOUT_SECONDS")


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)


def test_database_url_has_priority(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://otra/bd")
    monkeypatch.setenv("SUPABASE_DB_HOST", "ignorado")
    assert build_database_url() == "postgresql://otra/bd"


def test_supabase_defaults_port_5432_and_sslmode(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_USER", "usr")
    monkeypatch.setenv("SUPABASE_DB_PASSWORD", "pwd")
    monkeypatch.setenv("SUPABASE_DB_HOST", "host.ejemplo")
    assert build_database_url() == "postgresql+psycopg2://usr:pwd@host.ejemplo:5432/postgres?sslmode=require"


def test_user_and_password_are_escaped(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_USER", "postgres.ab@c")
    monkeypatch.setenv("SUPABASE_DB_PASSWORD", "p@ss/w ord%")
    monkeypatch.setenv("SUPABASE_DB_HOST", "h")
    monkeypatch.setenv("SUPABASE_DB_PORT", "6543")
    assert build_database_url() == "postgresql+psycopg2://postgres.ab%40c:p%40ss%2Fw+ord%25@h:6543/postgres?sslmode=require"


def test_connect_timeout_only_for_postgresql(monkeypatch):
    assert database_connect_args("postgresql+psycopg2://u:p@h/bd") == {"connect_timeout": 30}
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "5")
    assert database_connect_args("postgresql://u:p@h/bd") == {"connect_timeout": 5}
    assert database_connect_args("sqlite:///x.db") == {}


def test_alembic_config_keeps_escaped_url_intact():
    url = "postgresql+psycopg2://u:p%40ss%2F@h:5432/postgres?sslmode=require"
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # como migrations/env.py
    assert cfg.get_main_option("sqlalchemy.url") == url
