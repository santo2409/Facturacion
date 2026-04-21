from sqlalchemy.orm import Session

from src.shared.database.models import CompanyBillerModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaBillerCompanyRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def link_or_update(self, company_id, biller_id):
        try:
            row = self.session.query(CompanyBillerModel).filter_by(company_id=company_id).first()
            if row:
                row.biller_id = biller_id
            else:
                self.session.add(CompanyBillerModel(biller_id=biller_id, company_id=company_id))
            self.session.commit()
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error linking or updating biller-company relationship: {excep}",
                exc_info=True,
                user_msg="No se pudo vincular el facturador con la empresa.",
            )
            return None

    def all(self):
        try:
            rows = self.session.query(CompanyBillerModel).all()
            return [{"biller": r.biller_id, "company": r.company_id} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all billers: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener las vinculaciones.",
            )
            return None
