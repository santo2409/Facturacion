from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.special.domain.entities.special import Special


class PgSpecialRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM specials WHERE name = %s", (name,))
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error finding special by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el contrato especial. {name}",
            )
            return None

    def save(self, special):
        try:
            with self.conn.cursor() as cursor:
                exists = self.find_by_name(special.name)

                if exists:
                    special_id = exists[0]
                    cursor.execute(
                        "UPDATE specials SET name = %s WHERE id = %s",
                        (special.name, special_id),
                    )
                    self.conn.commit()
                    return Special(id=special_id, name=special.name)

                cursor.execute(
                    "INSERT INTO specials (name) VALUES (%s) RETURNING id",
                    (special.name,),
                )
                special_id = cursor.fetchone()[0]
                self.conn.commit()

                cursor.execute(
                    "SELECT id, name FROM specials WHERE id = %s", (special_id,)
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error saving special: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el contrato especial. {special.name}",
            )
            return None

    def update(self, special: Special) -> bool:
        try:
            if not special.id:
                self.logger.error(
                    "Special ID is required for update",
                    user_msg="No se puede actualizar sin identificador.",
                )
                return False

            with self.conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE specials SET name = %s WHERE id = %s",
                    (special.name, special.id),
                )
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as excep:
            self.logger.error(
                f"Error updating special: {excep}",
                exc_info=True,
                user_msg="No se pudo actualizar el contrato especial.",
            )
            return False

    def all(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM specials")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates specials: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de contratos especiales.",
            )
            return None
