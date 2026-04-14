from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLBillerCompanyRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def link_or_update(self, company_id, biller_id):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute(
                    "SELECT biller_id FROM companies_billers WHERE company_id = %s",
                    (company_id,),
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        "UPDATE companies_billers SET biller_id = %s WHERE company_id = %s",
                        (biller_id, company_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO companies_billers (biller_id, company_id) VALUES (%s, %s)",
                        (biller_id, company_id),
                    )
                self.conn.commit()
        except Exception as excep:
            self.logger.error(
                f"Error linking or updating biller-company relationship: {excep}",
                exc_info=True,
                user_msg="No se pudo vincular el facturador con la empresa.",
            )
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute("SELECT biller_id, company_id FROM companies_billers")
                results = cursor.fetchall()
                return [{"biller": row[0], "company": row[1]} for row in results]
        except Exception as excep:
            self.logger.error(f"Error retrieving all billers: {excep}", exc_info=True, user_msg="No se pudo obtener las vinculaciones.")
            return None
