from psycopg2.extras import execute_values

from src.billers.domain.entities.biller import Biller
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO billers (name) VALUES %s "
    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, name"
)


class PgBillerRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM billers WHERE name = %s", (name,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error finding biller: {e}", exc_info=True, user_msg=f"No se pudo consultar el facturador. {name}")
            return None

    def save(self, biller: Biller):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(biller.name,)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving biller: {e}", exc_info=True, user_msg=f"No se pudo guardar el facturador. {biller.name}")
            return None

    def save_batch(self, billers: list[Biller]):
        if not billers:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(b.name,) for b in billers], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch billers: {e}", exc_info=True, user_msg="No se pudieron guardar los facturadores.")
            return []

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM billers")
                return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving billers: {e}", exc_info=True, user_msg="No se pudo obtener el listado de facturadores.")
            return None
