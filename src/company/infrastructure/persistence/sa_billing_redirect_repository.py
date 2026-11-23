from sqlalchemy.orm import Session

from src.company.domain.repositories.billing_redirect_repository import (
    BillingRedirectRepository,
)
from src.shared.database.models import BillingRedirectModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaBillingRedirectRepository(BillingRedirectRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def all(self):
        try:
            rows = (
                self.session.query(BillingRedirectModel)
                .filter(BillingRedirectModel.deleted_at.is_(None))
                .all()
            )
            return [
                {
                    "nit_origen": r.nit_origen,
                    "nit_destino": r.nit_destino,
                    "etiqueta": r.etiqueta,
                    "name": r.name,
                }
                for r in rows
            ]
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error retrieving billing redirects: {e}",
                exc_info=True,
                user_msg="No se pudo consultar la tabla de redirecciones de facturación.",
            )
            return []
