from sqlalchemy.orm import Session

from src.company.domain.repositories.tian_repository import TianRepository
from src.shared.database.models import TianModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaTianRepository(TianRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def all(self):
        try:
            rows = (
                self.session.query(TianModel)
                .filter(TianModel.deleted_at.is_(None))
                .all()
            )
            return [{"nit_error": r.nit_error, "name": r.name} for r in rows]
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error retrieving tian companies: {e}",
                exc_info=True,
                user_msg="No se pudo consultar la tabla de empresas TIAN.",
            )
            return []
