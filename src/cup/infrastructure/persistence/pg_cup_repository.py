from src.cup.domain.repositories.cup_repository import CupRepository


class PgCupRepository(CupRepository):
    def __init__(self, conn):
        self.conn = conn

    def exists(self, cup: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cups WHERE code = %s LIMIT 1", (cup,))
            return cur.fetchone() is not None

    def get_all_cups(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT code FROM cups")
            return [row[0] for row in cur.fetchall()]

    def get_all(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, code, name FROM cups")
            return [{"id": r[0], "code": r[1], "name": r[2]} for r in cur.fetchall()]
