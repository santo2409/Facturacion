from psycopg2.extras import execute_values

from src.provider.domain.entities.provider import Provider
from src.provider.domain.repositories.provider_repository import ProviderRepository
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO providers (name) VALUES %s "
    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, name"
)


class PgProviderRepository(ProviderRepository):
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM providers WHERE name = %s", (name,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error finding provider: {e}", exc_info=True, user_msg=f"No se pudo consultar el proveedor. {name}")
            return None

    def save(self, provider: Provider):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(provider.name,)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving provider: {e}", exc_info=True, user_msg=f"No se pudo guardar el proveedor. {provider.name}")
            return None

    def save_batch(self, providers: list[Provider]):
        if not providers:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(p.name,) for p in providers], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch providers: {e}", exc_info=True, user_msg="No se pudieron guardar los proveedores.")
            return []

    def update(self, provider: Provider) -> bool:
        try:
            if not provider.id:
                return False
            with self.conn.cursor() as cur:
                cur.execute("UPDATE providers SET name = %s WHERE id = %s", (provider.name, provider.id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error updating provider: {e}", exc_info=True, user_msg="No se pudo actualizar el proveedor.")
            return False

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM providers")
                return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving providers: {e}", exc_info=True, user_msg="No se pudo obtener el listado de proveedores.")
            return None
