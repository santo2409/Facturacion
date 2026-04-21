from sqlalchemy.orm import Session

from src.rates.domain.entities.rate import Rate
from src.shared.database.models import RateModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaRatesRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, rate: Rate):
        try:
            row = self.session.query(RateModel).filter_by(
                rateable_id=rate.rateable_id,
                city_id=rate.city_id,
                cup_id=rate.cup_id,
                activity_id=rate.activity_id,
                rateable_type=rate.rateable_type,
            ).first()
            if not row:
                return None
            return (row.rateable_id, row.city_id, row.cup_id, row.rate, row.activity_id, row.rateable_type)
        except Exception as excep:
            self.logger.error(
                f"Error finding rate: {excep}",
                exc_info=True,
                user_msg="No se pudo consultar la tarifa.",
            )
            return None

    def save_batch(self, rates: list[Rate]):
        try:
            for r in rates:
                self.session.merge(RateModel(
                    rateable_id=r.rateable_id,
                    city_id=r.city_id,
                    cup_id=r.cup_id,
                    rate=r.rate,
                    activity_id=r.activity_id,
                    rateable_type=r.rateable_type,
                ))
            self.session.commit()
            return len(rates)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving batch rates: {excep}",
                exc_info=True,
                user_msg="No se pudieron guardar las tarifas.",
            )
            return 0
