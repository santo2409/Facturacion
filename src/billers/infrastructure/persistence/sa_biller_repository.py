from sqlalchemy.dialects.postgresql import insert
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
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error finding biller: {e}", exc_info=True, user_msg=f"No se pudo consultar el facturador. {name}")
            return None

    def save(self, biller: Biller):
        try:
            stmt = insert(BillerModel).values(name=biller.name)
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(BillerModel.id, BillerModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving biller: {e}", exc_info=True, user_msg=f"No se pudo guardar el facturador. {biller.name}")
            return None

    def save_batch(self, billers: list[Biller]):
        if not billers:
            return []
        try:
            stmt = insert(BillerModel).values([{"name": b.name} for b in billers])
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(BillerModel.id, BillerModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch billers: {e}", exc_info=True, user_msg="No se pudieron guardar los facturadores.")
            return []

    def all(self):
        try:
            rows = self.session.query(BillerModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error retrieving billers: {e}", exc_info=True, user_msg="No se pudo obtener el listado de facturadores.")
            return None
