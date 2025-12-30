from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.special.domain.entities.special import Special


class MySQLSpecialRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM specials WHERE name = %s", (name,))
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(f"Error finding special by name: {excep}", exc_info=True)
            return None

    def save(self, special):
        try:
            with self.conn.cursor(buffered=True) as cursor:
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
                    "INSERT INTO specials (name) VALUES (%s)", (special.name,)
                )
                self.conn.commit()

                special_id = cursor.lastrowid

                cursor.execute(
                    "SELECT id, name FROM specials WHERE id = %s", (special_id,)
                )

                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(f"Error saving special: {excep}", exc_info=True)
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM specials")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates specials: {excep}", exc_info=True
            )
            return None
