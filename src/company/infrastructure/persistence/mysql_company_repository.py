from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MySQLCompanyRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_nit(self, nit):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor.execute(
                    "SELECT id, nit, name FROM companies WHERE nit = %s", (nit,)
                )
                registered = cursor.fetchone()
                return registered
        except Exception as excep:
            self.logger.error(
                f"Error retrieving company by nit: {excep}", exc_info=True
            )
            return None

    def save(self, company):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                exists = self.find_by_nit(company.nit)

                if exists:
                    company_id = exists[0]
                    cursor.execute(
                        "UPDATE companies SET name = %s WHERE id = %s",
                        (company.name, company_id),
                    )
                    self.conn.commit()
                    return

                cursor.execute(
                    "INSERT INTO companies (nit, name) VALUES (%s, %s)",
                    (
                        company.nit,
                        company.name,
                    ),
                )
                self.conn.commit()

                company_id = cursor.lastrowid

                cursor.execute(
                    "SELECT id, nit, name FROM companies WHERE id = %s", (company_id,)
                )

                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(f"Error saving company: {excep}", exc_info=True)
            return None

    def all(self):
        try:
            with self.conn.cursor(buffered=True) as cursor:
                cursor = self.conn.cursor(buffered=True)
                cursor.execute("SELECT id, nit, name FROM companies")
                results = cursor.fetchall()
                return [
                    {"id": row[0], "nit": row[1], "name": row[2].upper()}
                    for row in results
                ]
        except Exception as excep:
            self.logger.error(f"Error retrieving all companies: {excep}", exc_info=True)
            return None
