from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLActivityRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute(
                    "SELECT id, name FROM type_activities WHERE name = %s", (name,)
                )
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(
                f"Error finding activity by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el tipo de actividad. {name}",
            )
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM type_activities")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all activities: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de actividades.",
            )
            return None
