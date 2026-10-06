from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.company.domain.repositories.imedical_repository import ImedicalRepository
from src.shared.database.models import ImedicalModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaImedicalRepository(ImedicalRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def all(self):
        try:
            rows = (
                self.session.query(ImedicalModel)
                .filter(ImedicalModel.deleted_at.is_(None))
                .all()
            )
            return [
                {
                    "nit_error": r.nit_error,
                    "name": r.name,
                    "nit_success": r.nit_success,
                    "name_error": r.name_error,
                }
                for r in rows
            ]
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error retrieving imedical corrections: {e}",
                exc_info=True,
                user_msg="No se pudo consultar la tabla de correcciones i-medical.",
            )
            return []

    def save_batch(self, corrections):
        if not corrections:
            return 0
        try:
            stmt = insert(ImedicalModel).values([
                {
                    "nit_error": c.nit_error,
                    "nit_success": c.nit_success,
                    "name": c.name,
                    "name_error": c.name_error,
                }
                for c in corrections
            ])
            stmt = stmt.on_conflict_do_update(
                index_elements=["nit_error"],
                set_={
                    "nit_success": stmt.excluded.nit_success,
                    "name": stmt.excluded.name,
                    "name_error": stmt.excluded.name_error,
                    "updated_at": func.now(),
                },
            )
            self.session.execute(stmt)
            self.session.commit()
            return len(corrections)
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error saving imedical corrections batch: {e}",
                exc_info=True,
                user_msg="No se pudieron registrar las correcciones i-medical.",
            )
            return 0
