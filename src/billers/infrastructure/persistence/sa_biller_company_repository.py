from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.shared.database.models import CompanyBillerModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaBillerCompanyRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def link_or_update_batch(self, pairs):
        """pairs: list of (company_id, biller_id)"""
        if not pairs:
            return
        try:
            stmt = insert(CompanyBillerModel).values([{"company_id": p[0], "biller_id": p[1]} for p in pairs])
            stmt = stmt.on_conflict_do_update(index_elements=["company_id"], set_={"biller_id": stmt.excluded.biller_id})
            self.session.execute(stmt)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error batch linking biller-company: {e}", exc_info=True, user_msg="No se pudieron vincular los facturadores.")

    def all(self):
        try:
            rows = self.session.query(CompanyBillerModel).all()
            return [{"biller": r.biller_id, "company": r.company_id} for r in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving biller-company links: {e}", exc_info=True, user_msg="No se pudo obtener las vinculaciones.")
            return None
