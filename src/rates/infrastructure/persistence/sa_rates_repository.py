from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.rates.domain.entities.rate import Rate
from src.shared.database.models import RateModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_BATCH_CHUNK = 500


class SaRatesRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, rate: Rate):
        try:
            row = self.session.query(RateModel).filter_by(
                rateable_id=rate.rateable_id, city_id=rate.city_id,
                cup_id=rate.cup_id, activity_id=rate.activity_id,
                rateable_type=rate.rateable_type,
            ).first()
            if not row:
                return None
            return (row.rateable_id, row.city_id, row.cup_id, row.rate, row.activity_id, row.rateable_type)
        except Exception as excep:
            self.logger.error(f"Error finding rate: {excep}", exc_info=True, user_msg="No se pudo consultar la tarifa.")
            return None

    def find_batch(self, keys: list[tuple]) -> dict[tuple, int]:
        """Fetch rates for multiple composite keys in chunked queries.

        keys: list of (rateable_id, city_id, cup_id, activity_id, rateable_type)
        Returns: dict mapping key tuple → rate value
        """
        if not keys:
            return {}
        result = {}
        try:
            for i in range(0, len(keys), _BATCH_CHUNK):
                chunk = keys[i:i + _BATCH_CHUNK]
                rows = (
                    self.session.query(
                        RateModel.rateable_id, RateModel.city_id,
                        RateModel.cup_id, RateModel.rate,
                        RateModel.activity_id, RateModel.rateable_type,
                    )
                    .filter(
                        tuple_(
                            RateModel.rateable_id, RateModel.city_id,
                            RateModel.cup_id, RateModel.activity_id,
                            RateModel.rateable_type,
                        ).in_(chunk)
                    )
                    .all()
                )
                for r in rows:
                    key = (r[0], r[1], r[2], r[4], r[5])
                    result[key] = r[3]
        except Exception as excep:
            self.logger.error(f"Error in find_batch: {excep}", exc_info=True, user_msg="No se pudieron consultar las tarifas en lote.")
        return result

    def save_batch(self, rates: list[Rate]):
        if not rates:
            return 0
        try:
            stmt = insert(RateModel).values([
                dict(rateable_id=r.rateable_id, city_id=r.city_id, cup_id=r.cup_id,
                     rate=r.rate, activity_id=r.activity_id, rateable_type=r.rateable_type)
                for r in rates
            ])
            stmt = stmt.on_conflict_do_update(
                index_elements=["rateable_id", "city_id", "cup_id", "activity_id", "rateable_type"],
                set_={"rate": stmt.excluded.rate},
            )
            self.session.execute(stmt)
            self.session.commit()
            return len(rates)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(f"Error saving batch rates: {excep}", exc_info=True, user_msg="No se pudieron guardar las tarifas.")
            return 0
