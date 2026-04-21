from sqlalchemy.orm import Session

from src.shared.database.models import TypeActivityModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaActivityRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(TypeActivityModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as excep:
            self.logger.error(
                f"Error finding activity by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el tipo de actividad. {name}",
            )
            return None

    def all(self):
        try:
            rows = self.session.query(TypeActivityModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all activities: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de actividades.",
            )
            return None
