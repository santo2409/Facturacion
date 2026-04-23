from sqlalchemy import text


def test_pg_connection(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


def test_sa_session(sa_session):
    result = sa_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
