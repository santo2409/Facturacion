from sqlalchemy.orm import Session

from src.billers.domain.entities.biller import Biller
from src.shared.database.models import BillerModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaBillerRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(BillerModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as excep:
            self.logger.error(
                f"Error finding biller by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el facturador. {name}",
            )
            return None

    def save(self, biller: Biller):
        try:
            exists = self.find_by_name(biller.name)
            if exists:
                obj = self.session.query(BillerModel).get(exists[0])
                obj.name = biller.name
                self.session.commit()
                return Biller(id=obj.id, name=obj.name)

            obj = BillerModel(name=biller.name)
            self.session.add(obj)
            self.session.commit()
            return (obj.id, obj.name)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving biller: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el facturador. {biller.name}",
            )
            return None

    def all(self):
        try:
            rows = self.session.query(BillerModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all billers: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de facturadores.",
            )
            return None
