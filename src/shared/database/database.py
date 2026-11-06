import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

load_dotenv(override=True)


def _build_url():
    user = os.getenv("SUPABASE_DB_USER")
    password = quote_plus(os.getenv("SUPABASE_DB_PASSWORD", ""))
    host = os.getenv("SUPABASE_DB_HOST")
    port = os.getenv("SUPABASE_DB_PORT", 5432)
    name = os.getenv("SUPABASE_DB_NAME", "postgres")
    return (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}?sslmode=require"
    )


engine = create_engine(_build_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()
