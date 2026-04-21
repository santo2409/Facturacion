from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class PgCompanyRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_nit(self, nit):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, nit, name FROM companies WHERE nit = %s", (nit,)
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error retrieving company by nit: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar la empresa. NIT {nit}",
            )
            return None

    def save(self, company):
        try:
            with self.conn.cursor() as cursor:
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
                    "INSERT INTO companies (nit, name) VALUES (%s, %s) RETURNING id",
                    (company.nit, company.name),
                )
                company_id = cursor.fetchone()[0]
                self.conn.commit()

                cursor.execute(
                    "SELECT id, nit, name FROM companies WHERE id = %s", (company_id,)
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error saving company: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar la empresa. {company.name}",
            )
            return None

    def all(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT id, nit, name FROM companies")
                results = cursor.fetchall()
                return [
                    {"id": row[0], "nit": row[1], "name": row[2].upper()}
                    for row in results
                ]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all companies: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de empresas.",
            )
            return None

    def find_by_id(self, id):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT company_id, package_id, model FROM companies_packages WHERE company_id = %s",
                    (id,),
                )
                return cursor.fetchone()
        except Exception as excep:
            self.logger.error(
                f"Error retrieving company by id: {excep}",
                exc_info=True,
                user_msg="No se pudo consultar la empresa.",
            )
            return None

    def companies_packages(self, relations):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO companies_packages (company_id, package_id, model) VALUES (%s, %s, %s) "
                    "ON CONFLICT (company_id) DO UPDATE SET package_id = EXCLUDED.package_id, model = EXCLUDED.model",
                    (relations.company_id, relations.package_id, relations.model),
                )
                self.conn.commit()
        except Exception as excep:
            self.logger.error(
                f"Error saving companies_packages: {excep}",
                exc_info=True,
                user_msg="No se pudo vincular la empresa con el paquete.",
            )
            return None

    def companies_packages_all(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT company_id, package_id, model FROM companies_packages"
                )
                results = cursor.fetchall()
                return [
                    {"company": row[0], "package": row[1], "model": row[2]}
                    for row in results
                ]
        except Exception as excep:
            self.logger.error(
                f"Error searching companies_packages: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener las vinculaciones de empresas.",
            )
            return None
