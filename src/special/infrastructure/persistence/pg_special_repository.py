from psycopg2.extras import execute_values

from src.special.domain.entities.special import Special
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO specials (name) VALUES %s "
    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, name"
)


class PgSpecialRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM specials WHERE name = %s", (name,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error finding special: {e}", exc_info=True, user_msg=f"No se pudo consultar el contrato especial. {name}")
            return None

    def save(self, special: Special):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(special.name,)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving special: {e}", exc_info=True, user_msg=f"No se pudo guardar el contrato especial. {special.name}")
            return None

    def save_batch(self, specials: list[Special]):
        if not specials:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(s.name,) for s in specials], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch specials: {e}", exc_info=True, user_msg="No se pudieron guardar los contratos especiales.")
            return []

    def update(self, special: Special) -> bool:
        try:
            if not special.id:
                return False
            with self.conn.cursor() as cur:
                cur.execute("UPDATE specials SET name = %s WHERE id = %s", (special.name, special.id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error updating special: {e}", exc_info=True, user_msg="No se pudo actualizar el contrato especial.")
            return False

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM specials")
                return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving specials: {e}", exc_info=True, user_msg="No se pudo obtener el listado de contratos especiales.")
            return None
