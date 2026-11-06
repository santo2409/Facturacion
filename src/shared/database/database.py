import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.shared.env import load_env

Base = declarative_base()

load_env()


DEFAULT_DB_PORT = "5432"


def build_database_url() -> str:
    """URL de la BD desde SUPABASE_DB_* (AUD-45): usuario y contraseña escapados,
    puerto 5432 por defecto y sslmode=require. La app no lee DATABASE_URL; Alembic
    la usa si existe y, si no, usa esta misma función (migrations/env.py).
    """
    user = quote_plus(os.getenv("SUPABASE_DB_USER", ""))
    password = quote_plus(os.getenv("SUPABASE_DB_PASSWORD", ""))
    host = os.getenv("SUPABASE_DB_HOST")
    port = os.getenv("SUPABASE_DB_PORT", DEFAULT_DB_PORT)
    name = os.getenv("SUPABASE_DB_NAME", "postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}?sslmode=require"


engine = create_engine(build_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()
