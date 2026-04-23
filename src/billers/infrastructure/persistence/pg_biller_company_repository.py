from psycopg2.extras import execute_values

from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO companies_billers (company_id, biller_id) VALUES %s "
    "ON CONFLICT (company_id) DO UPDATE SET biller_id = EXCLUDED.biller_id"
)


class PgBillerCompanyRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def link_or_update(self, company_id, biller_id):
        try:
            with self.conn.cursor() as cur:
                execute_values(cur, _UPSERT_SQL, [(company_id, biller_id)])
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error linking biller-company: {e}", exc_info=True, user_msg="No se pudo vincular el facturador con la empresa.")
            return None

    def link_or_update_batch(self, pairs):
        """pairs: list of (company_id, biller_id)"""
        if not pairs:
            return
        try:
            with self.conn.cursor() as cur:
                execute_values(cur, _UPSERT_SQL, pairs, page_size=1000)
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error batch linking biller-company: {e}", exc_info=True, user_msg="No se pudieron vincular los facturadores.")

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT biller_id, company_id FROM companies_billers")
                return [{"biller": r[0], "company": r[1]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving biller-company links: {e}", exc_info=True, user_msg="No se pudo obtener las vinculaciones.")
            return None
