import os
import pytest
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(override=True)

from src.shared.database.models import Base


def _pg_conn_params():
    return dict(
        host=os.getenv("SUPABASE_DB_HOST"),
        port=os.getenv("SUPABASE_DB_PORT", "6543"),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
        options="-c search_path=public",
    )


@pytest.fixture
def pg_conn():
    conn = psycopg2.connect(**_pg_conn_params())
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def sa_session():
    import urllib.parse
    p = _pg_conn_params()
    password = urllib.parse.quote_plus(p["password"] or "")
    url = f"postgresql+psycopg2://{p['user']}:{password}@{p['host']}:{p['port']}/{p['dbname']}?sslmode=require"
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
