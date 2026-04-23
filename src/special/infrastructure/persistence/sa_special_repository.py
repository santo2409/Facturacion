from sqlalchemy.dialects.postgresql import insert
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
        except Exception as e:
            self.logger.error(f"Error finding special: {e}", exc_info=True, user_msg=f"No se pudo consultar el contrato especial. {name}")
            return None

    def save(self, special: Special):
        try:
            stmt = insert(SpecialModel).values(name=special.name)
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(SpecialModel.id, SpecialModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving special: {e}", exc_info=True, user_msg=f"No se pudo guardar el contrato especial. {special.name}")
            return None

    def save_batch(self, specials: list[Special]):
        if not specials:
            return []
        try:
            stmt = insert(SpecialModel).values([{"name": s.name} for s in specials])
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(SpecialModel.id, SpecialModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch specials: {e}", exc_info=True, user_msg="No se pudieron guardar los contratos especiales.")
            return []

    def update(self, special: Special) -> bool:
        try:
            if not special.id:
                return False
            obj = self.session.query(SpecialModel).get(special.id)
            if not obj:
                return False
            obj.name = special.name
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error updating special: {e}", exc_info=True, user_msg="No se pudo actualizar el contrato especial.")
            return False

    def all(self):
        try:
            rows = self.session.query(SpecialModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving specials: {e}", exc_info=True, user_msg="No se pudo obtener el listado de contratos especiales.")
            return None
