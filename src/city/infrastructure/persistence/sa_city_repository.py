from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.city.domain.entities.city import City
from src.shared.database.models import CityModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaCityRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(CityModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as e:
            self.logger.error(f"Error finding city: {e}", exc_info=True, user_msg=f"No se pudo consultar la ciudad. {name}")
            return None

    def save(self, city: City):
        try:
            stmt = insert(CityModel).values(name=city.name)
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(CityModel.id, CityModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving city: {e}", exc_info=True, user_msg=f"No se pudo guardar la ciudad. {city.name}")
            return None

    def save_batch(self, cities: list[City]):
        if not cities:
            return []
        try:
            stmt = insert(CityModel).values([{"name": c.name} for c in cities])
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(CityModel.id, CityModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch cities: {e}", exc_info=True, user_msg="No se pudieron guardar las ciudades.")
            return []

    def all(self):
        try:
            rows = self.session.query(CityModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving cities: {e}", exc_info=True, user_msg="No se pudo obtener el listado de ciudades.")
            return None
