from src.rates.domain.entities.rate import Rate
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLRatesRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, rate: Rate):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute(
                    "SELECT * FROM rates WHERE rateable_id = %s and city_id = %s and cup_id = %s and activity_id = %s and rateable_type = %s",
                    (
                        rate.rateable_id,
                        rate.city_id,
                        rate.cup_id,
                        rate.activity_id,
                        rate.rateable_type,
                    ),
                )
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(f"Error finding city by name: {excep}", exc_info=True)
            return None

    def save_batch(self, rates: list[Rate]):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                # Inserción por lotes
                values = [
                    (
                        r.rateable_id,
                        r.city_id,
                        r.cup_id,
                        r.rate,
                        r.activity_id,
                        r.rateable_type,
                    )
                    for r in rates
                ]

                cursor.executemany(
                    "INSERT INTO rates (rateable_id, city_id, cup_id, rate, activity_id, rateable_type) "
                    "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE rate = VALUES(rate)",
                    values,
                )
                self.conn.commit()
                return cursor.rowcount
        except Exception as excep:
            self.logger.error(f"Error saving batch rates: {excep}", exc_info=True)
            return 0
