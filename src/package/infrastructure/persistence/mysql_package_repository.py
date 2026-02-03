from src.package.domain.entities.package import Package
from src.package.domain.repositories.package_repository import PackageRepository
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLPackageRepository(PackageRepository):
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM packages WHERE name = %s", (name,))
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(f"Error finding package by name: {excep}", exc_info=True)
            return None

    def save(self, package: Package):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                exists = self.find_by_name(package.name)

                if exists:
                    package_id = exists[0]
                    cursor.execute(
                        "UPDATE packages SET name = %s WHERE id = %s",
                        (package.name, package_id),
                    )
                    self.conn.commit()
                    return Package(id=package_id, name=package.name)

                cursor.execute(
                    "INSERT INTO packages (name) VALUES (%s)", (package.name,)
                )
                self.conn.commit()

                package_id = cursor.lastrowid

                cursor.execute(
                    "SELECT id, name FROM packages WHERE id = %s", (package_id,)
                )

                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(f"Error saving package: {excep}", exc_info=True)
            return None

    def update(self, package: Package) -> bool:
        try:
            if not package.id:
                self.logger.error("Package ID is required for update")
                return False
                
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute(
                    "UPDATE packages SET name = %s WHERE id = %s",
                    (package.name, package.id),
                )
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as excep:
            self.logger.error(f"Error updating package: {excep}", exc_info=True)
            return False

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM packages")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates packages: {excep}", exc_info=True
            )
            return None
