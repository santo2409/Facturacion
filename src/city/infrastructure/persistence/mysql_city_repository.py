from src.city.domain.entities.city import City
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLCityRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM cities WHERE name = %s", (name,))
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(f"Error finding city by name: {excep}", exc_info=True)
            return None

    def save(self, city: City):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                exists = self.find_by_name(city.name)

                if exists:
                    city_id = exists[0]
                    cursor.execute(
                        "UPDATE cities SET name = %s WHERE id = %s",
                        (city.name, city_id),
                    )
                    self.conn.commit()
                    return City(id=city_id, name=city.name)

                cursor.execute("INSERT INTO cities (name) VALUES (%s)", (city.name,))
                self.conn.commit()

                city_id = cursor.lastrowid

                cursor.execute("SELECT id, name FROM cities WHERE id = %s", (city_id,))

                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(f"Error saving city: {excep}", exc_info=True)
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT id, name FROM cities")
                results = cursor.fetchall()
                return [{"id": row[0], "name": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(f"Error retrieving all cities: {excep}", exc_info=True)
            return None
