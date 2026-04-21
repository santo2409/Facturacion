from sqlalchemy.orm import Session

from src.shared.database.models import SpecialModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.special.domain.entities.special import Special


class SaSpecialRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(SpecialModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as excep:
            self.logger.error(
                f"Error finding special by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el contrato especial. {name}",
            )
            return None

    def save(self, special):
        try:
            exists = self.find_by_name(special.name)
            if exists:
                obj = self.session.query(SpecialModel).get(exists[0])
                obj.name = special.name
                self.session.commit()
                return Special(id=obj.id, name=obj.name)

            obj = SpecialModel(name=special.name)
            self.session.add(obj)
            self.session.commit()
            return (obj.id, obj.name)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving special: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el contrato especial. {special.name}",
            )
            return None

    def update(self, special: Special) -> bool:
        try:
            if not special.id:
                self.logger.error("Special ID is required for update", user_msg="No se puede actualizar sin identificador.")
                return False
            obj = self.session.query(SpecialModel).get(special.id)
            if not obj:
                return False
            obj.name = special.name
            self.session.commit()
            return True
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error updating special: {excep}",
                exc_info=True,
                user_msg="No se pudo actualizar el contrato especial.",
            )
            return False

    def all(self):
        try:
            rows = self.session.query(SpecialModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates specials: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de contratos especiales.",
            )
            return None
