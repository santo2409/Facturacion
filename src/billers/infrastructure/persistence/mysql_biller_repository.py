from src.billers.domain.entities.biller import Biller
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLBillerRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM billers WHERE name = %s", (name,))
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(
                f"Error finding biller by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el facturador. {name}",
            )
            return None

    def save(self, biller: Biller):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                exists = self.find_by_name(biller.name)

                if exists:
                    biller_id = exists[0]
                    cursor.execute(
                        "UPDATE billers SET name = %s WHERE id = %s",
                        (biller.name, biller_id),
                    )
                    self.conn.commit()
                    return Biller(id=biller_id, name=biller.name)

                cursor.execute("INSERT INTO billers (name) VALUES (%s)", (biller.name,))
                self.conn.commit()

                biller_id = cursor.lastrowid

                cursor.execute(
                    "SELECT id, name FROM billers WHERE id = %s", (biller_id,)
                )

                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error saving biller: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el facturador. {biller.name}",
            )
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM billers")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all billers: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de facturadores.",
            )
            return None
