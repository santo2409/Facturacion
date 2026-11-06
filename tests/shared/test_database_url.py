"""AUD-45: regla de URL de BD de la app y de Alembic (credenciales ficticias)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config

from src.shared.database.database import build_database_url

ROOT = Path(__file__).resolve().parents[2]

_VARS = ("DATABASE_URL", "SUPABASE_DB_USER", "SUPABASE_DB_PASSWORD", "SUPABASE_DB_HOST",
         "SUPABASE_DB_PORT", "SUPABASE_DB_NAME")


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)


def test_app_ignores_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://otra/bd")
    monkeypatch.setenv("SUPABASE_DB_HOST", "host.ejemplo")
    assert build_database_url().startswith("postgresql+psycopg2://")
    assert "@host.ejemplo:5432/" in build_database_url()


def test_alembic_uses_database_url_when_present():
    # Modo offline: el SQL generado no conecta; un dialecto distinto prueba que se usó DATABASE_URL.
    entorno = {**os.environ, "DATABASE_URL": "sqlite:///ficticia.db"}
    ddl = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT, capture_output=True, text=True, env=entorno,
    )
    assert "Context impl SQLiteImpl" in ddl.stderr


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


def test_alembic_config_keeps_escaped_url_intact():
    url = "postgresql+psycopg2://u:p%40ss%2F@h:5432/postgres?sslmode=require"
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # como migrations/env.py
    assert cfg.get_main_option("sqlalchemy.url") == url
