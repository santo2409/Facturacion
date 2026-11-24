from sqlalchemy import func
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

    def upsert_many(self, rows):
        nuevas = actualizadas = 0
        try:
            for row in rows:
                existente = self.session.get(BillingRedirectModel, row["nit_origen"])
                if existente is None:
                    self.session.add(BillingRedirectModel(
                        nit_origen=row["nit_origen"], nit_destino=row["nit_destino"],
                        etiqueta=row["etiqueta"], name=row.get("name"),
                    ))
                    nuevas += 1
                else:
                    existente.nit_destino = row["nit_destino"]
                    existente.etiqueta = row["etiqueta"]
                    existente.name = row.get("name")
                    existente.deleted_at = None
                    existente.updated_at = func.now()
                    actualizadas += 1
            self.session.commit()
            return nuevas, actualizadas
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error saving billing redirects: {e}",
                exc_info=True,
                user_msg="No se pudieron guardar las redirecciones de facturación; no se guardó ninguna fila.",
            )
            return None

    def deactivate(self, nits_origen):
        desactivadas = []
        try:
            for nit in nits_origen:
                existente = self.session.get(BillingRedirectModel, nit)
                if existente is not None and existente.deleted_at is None:
                    existente.deleted_at = func.now()
                    existente.updated_at = func.now()
                    desactivadas.append(nit)
            self.session.commit()
            return desactivadas
        except Exception as e:
            self.session.rollback()
            self.logger.error(
                f"Error deactivating billing redirects: {e}",
                exc_info=True,
                user_msg="No se pudieron desactivar las redirecciones indicadas.",
            )
            return None
