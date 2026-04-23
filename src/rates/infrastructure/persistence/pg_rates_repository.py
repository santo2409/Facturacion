from psycopg2.extras import execute_values

from src.rates.domain.entities.rate import Rate
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class PgRatesRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, rate: Rate):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT rateable_id, city_id, cup_id, rate, activity_id, rateable_type "
                    "FROM rates WHERE rateable_id = %s AND city_id = %s AND cup_id = %s "
                    "AND activity_id = %s AND rateable_type = %s",
                    (rate.rateable_id, rate.city_id, rate.cup_id, rate.activity_id, rate.rateable_type),
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(f"Error finding rate: {excep}", exc_info=True, user_msg="No se pudo consultar la tarifa.")
            return None

    def save_batch(self, rates: list[Rate]):
        if not rates:
            return 0
        try:
            with self.conn.cursor() as cursor:
                execute_values(
                    cursor,
                    "INSERT INTO rates (rateable_id, city_id, cup_id, rate, activity_id, rateable_type) "
                    "VALUES %s "
                    "ON CONFLICT (rateable_id, city_id, cup_id, activity_id, rateable_type) "
                    "DO UPDATE SET rate = EXCLUDED.rate",
                    [(r.rateable_id, r.city_id, r.cup_id, r.rate, r.activity_id, r.rateable_type) for r in rates],
                    page_size=1000,
                )
                self.conn.commit()
                return len(rates)
        except Exception as excep:
            self.conn.rollback()
            self.logger.error(f"Error saving batch rates: {excep}", exc_info=True, user_msg="No se pudieron guardar las tarifas.")
            return 0
