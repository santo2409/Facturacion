from src.provider.domain.entities.provider import Provider
from src.provider.domain.repositories.provider_repository import ProviderRepository
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class PgProviderRepository(ProviderRepository):
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, name FROM providers WHERE name = %s", (name,)
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error finding provider by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el proveedor. {name}",
            )
            return None

    def save(self, provider):
        try:
            with self.conn.cursor() as cursor:
                exists = self.find_by_name(provider.name)

                if exists:
                    provider_id = exists[0]
                    cursor.execute(
                        "UPDATE providers SET name = %s WHERE id = %s",
                        (provider.name, provider_id),
                    )
                    self.conn.commit()
                    return Provider(id=provider_id, name=provider.name)

                cursor.execute(
                    "INSERT INTO providers (name) VALUES (%s) RETURNING id",
                    (provider.name,),
                )
                provider_id = cursor.fetchone()[0]
                self.conn.commit()

                cursor.execute(
                    "SELECT id, name FROM providers WHERE id = %s", (provider_id,)
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error saving provider: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el proveedor. {provider.name}",
            )
            return None

    def update(self, provider: Provider) -> bool:
        try:
            if not provider.id:
                self.logger.error(
                    "Provider ID is required for update",
                    user_msg="No se puede actualizar sin identificador.",
                )
                return False

            with self.conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE providers SET name = %s WHERE id = %s",
                    (provider.name, provider.id),
                )
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as excep:
            self.logger.error(
                f"Error updating provider: {excep}",
                exc_info=True,
                user_msg="No se pudo actualizar el proveedor.",
            )
            return False

    def all(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM providers")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates providers: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de proveedores.",
            )
            return None
