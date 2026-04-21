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
        except Exception as excep:
            self.logger.error(
                f"Error finding city by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar la ciudad. {name}",
            )
            return None

    def save(self, city: City):
        try:
            exists = self.find_by_name(city.name)
            if exists:
                obj = self.session.query(CityModel).get(exists[0])
                obj.name = city.name
                self.session.commit()
                return City(id=obj.id, name=obj.name)

            obj = CityModel(name=city.name)
            self.session.add(obj)
            self.session.commit()
            return (obj.id, obj.name)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving city: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar la ciudad. {city.name}",
            )
            return None

    def all(self):
        try:
            rows = self.session.query(CityModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all cities: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de ciudades.",
            )
            return None
