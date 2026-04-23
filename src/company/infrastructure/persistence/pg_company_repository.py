from psycopg2.extras import execute_values

from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

_UPSERT_SQL = (
    "INSERT INTO companies (nit, name) VALUES %s "
    "ON CONFLICT (nit) DO UPDATE SET name = EXCLUDED.name "
    "RETURNING id, nit, name"
)

_UPSERT_PKG_SQL = (
    "INSERT INTO companies_packages (company_id, package_id, model) VALUES %s "
    "ON CONFLICT (company_id) DO UPDATE SET package_id = EXCLUDED.package_id, model = EXCLUDED.model"
)


class PgCompanyRepository:
    def __init__(self, conn, logger: LoggerAdapter = None):
        self.conn = conn
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_nit(self, nit):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, nit, name FROM companies WHERE nit = %s", (nit,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error retrieving company by nit: {e}", exc_info=True, user_msg=f"No se pudo consultar la empresa. NIT {nit}")
            return None

    def save(self, company):
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(company.nit, company.name)], fetch=True)
                self.conn.commit()
                return rows[0] if rows else None
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving company: {e}", exc_info=True, user_msg=f"No se pudo guardar la empresa. {company.name}")
            return None

    def save_batch(self, companies):
        if not companies:
            return []
        try:
            with self.conn.cursor() as cur:
                rows = execute_values(cur, _UPSERT_SQL, [(c.nit, c.name) for c in companies], fetch=True)
                self.conn.commit()
                return rows
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving batch companies: {e}", exc_info=True, user_msg="No se pudieron guardar las empresas.")
            return []

    def all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, nit, name FROM companies")
                return [{"id": r[0], "nit": r[1], "name": r[2].upper()} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving companies: {e}", exc_info=True, user_msg="No se pudo obtener el listado de empresas.")
            return None

    def find_by_id(self, id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT company_id, package_id, model FROM companies_packages WHERE company_id = %s", (id,))
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error retrieving company by id: {e}", exc_info=True, user_msg="No se pudo consultar la empresa.")
            return None

    def companies_packages(self, relations):
        try:
            with self.conn.cursor() as cur:
                execute_values(cur, _UPSERT_PKG_SQL, [(relations.company_id, relations.package_id, relations.model)])
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving companies_packages: {e}", exc_info=True, user_msg="No se pudo vincular la empresa con el paquete.")
            return None

    def companies_packages_all(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT company_id, package_id, model FROM companies_packages")
                return [{"company": r[0], "package": r[1], "model": r[2]} for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error searching companies_packages: {e}", exc_info=True, user_msg="No se pudo obtener las vinculaciones de empresas.")
            return None
