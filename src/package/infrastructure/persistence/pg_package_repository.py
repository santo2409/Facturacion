from psycopg2.extras import execute_values

from src.package.domain.entities.package import Package
from src.package.domain.repositories.package_repository import PackageRepository
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO packages (name) VALUES %s "
    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, name"
)


class PgPackageRepository(PackageRepository):
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM packages WHERE name = %s", (name,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error finding package: {e}", exc_info=True, user_msg=f"No se pudo consultar el paquete. {name}")
            return None

    def save(self, package: Package):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(package.name,)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving package: {e}", exc_info=True, user_msg=f"No se pudo guardar el paquete. {package.name}")
            return None

    def save_batch(self, packages: list[Package]):
        if not packages:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(p.name,) for p in packages], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch packages: {e}", exc_info=True, user_msg="No se pudieron guardar los paquetes.")
            return []

    def update(self, package: Package) -> bool:
        try:
            if not package.id:
                return False
            with self.conn.cursor() as cur:
                cur.execute("UPDATE packages SET name = %s WHERE id = %s", (package.name, package.id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error updating package: {e}", exc_info=True, user_msg="No se pudo actualizar el paquete.")
            return False

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, name FROM packages")
                return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving packages: {e}", exc_info=True, user_msg="No se pudo obtener el listado de paquetes.")
            return None
