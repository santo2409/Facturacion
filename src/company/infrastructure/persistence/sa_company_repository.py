from sqlalchemy.orm import Session

from src.shared.database.models import CompanyModel, CompanyPackageModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaCompanyRepository:
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_nit(self, nit):
        try:
            row = self.session.query(CompanyModel).filter_by(nit=nit).first()
            return (row.id, row.nit, row.name) if row else None
        except Exception as excep:
            self.logger.error(
                f"Error retrieving company by nit: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar la empresa. NIT {nit}",
            )
            return None

    def save(self, company):
        try:
            exists = self.find_by_nit(company.nit)
            if exists:
                obj = self.session.query(CompanyModel).get(exists[0])
                obj.name = company.name
                self.session.commit()
                return

            obj = CompanyModel(nit=company.nit, name=company.name)
            self.session.add(obj)
            self.session.commit()
            return (obj.id, obj.nit, obj.name)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving company: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar la empresa. {company.name}",
            )
            return None

    def all(self):
        try:
            rows = self.session.query(CompanyModel).all()
            return [{"id": r.id, "nit": r.nit, "name": r.name.upper()} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all companies: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de empresas.",
            )
            return None

    def find_by_id(self, id):
        try:
            row = self.session.query(CompanyPackageModel).filter_by(company_id=id).first()
            return (row.company_id, row.package_id, row.model) if row else None
        except Exception as excep:
            self.logger.error(
                f"Error retrieving company by id: {excep}",
                exc_info=True,
                user_msg="No se pudo consultar la empresa.",
            )
            return None

    def companies_packages(self, relations):
        try:
            row = self.session.query(CompanyPackageModel).filter_by(company_id=relations.company_id).first()
            if row:
                row.package_id = relations.package_id
                row.model = relations.model
            else:
                self.session.add(CompanyPackageModel(
                    company_id=relations.company_id,
                    package_id=relations.package_id,
                    model=relations.model,
                ))
            self.session.commit()
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving companies_packages: {excep}",
                exc_info=True,
                user_msg="No se pudo vincular la empresa con el paquete.",
            )
            return None

    def companies_packages_all(self):
        try:
            rows = self.session.query(CompanyPackageModel).all()
            return [{"company": r.company_id, "package": r.package_id, "model": r.model} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error searching companies_packages: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener las vinculaciones de empresas.",
            )
            return None
