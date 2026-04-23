from psycopg2.extras import execute_values

from src.city.domain.entities.city import City
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO cities (name) VALUES %s "
    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, name"
)


class PgCityRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM cities WHERE name = %s", (name,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error finding city: {e}", exc_info=True, user_msg=f"No se pudo consultar la ciudad. {name}")
            return None

    def save(self, city: City):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(city.name,)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving city: {e}", exc_info=True, user_msg=f"No se pudo guardar la ciudad. {city.name}")
            return None

    def save_batch(self, cities: list[City]):
        if not cities:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(c.name,) for c in cities], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch cities: {e}", exc_info=True, user_msg="No se pudieron guardar las ciudades.")
            return []

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM cities")
                return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving cities: {e}", exc_info=True, user_msg="No se pudo obtener el listado de ciudades.")
            return None
