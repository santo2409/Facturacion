import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.shared.config import get_int_env
from src.shared.env import load_env

Base = declarative_base()

load_env()


DEFAULT_DB_PORT = "5432"
DEFAULT_DB_CONNECT_TIMEOUT_SECONDS = 30


def build_database_url() -> str:
    """URL única de la BD para la app y para Alembic (AUD-45).

    DATABASE_URL, si existe, se usa tal cual. Si no, se arma con SUPABASE_DB_*:
    usuario y contraseña escapados, puerto 5432 por defecto y sslmode=require.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = quote_plus(os.getenv("SUPABASE_DB_USER", ""))
    password = quote_plus(os.getenv("SUPABASE_DB_PASSWORD", ""))
    host = os.getenv("SUPABASE_DB_HOST")
    port = os.getenv("SUPABASE_DB_PORT", DEFAULT_DB_PORT)
    name = os.getenv("SUPABASE_DB_NAME", "postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}?sslmode=require"


def database_connect_args(url: str) -> dict:
    """connect_timeout solo para PostgreSQL (otros drivers no aceptan ese argumento)."""
    if not url.startswith("postgresql"):
        return {}
    return {"connect_timeout": get_int_env("DB_CONNECT_TIMEOUT_SECONDS", DEFAULT_DB_CONNECT_TIMEOUT_SECONDS)}


_url = build_database_url()
engine = create_engine(_url, pool_pre_ping=True, connect_args=database_connect_args(_url))
SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()
