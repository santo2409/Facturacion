from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.company.domain.repositories.company_repository import CompanyRepository
from src.shared.database.models import CompanyModel, CompanyPackageModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaCompanyRepository(CompanyRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_nit(self, nit):
        try:
            row = self.session.query(CompanyModel).filter_by(nit=nit).first()
            return (row.id, row.nit, row.name) if row else None
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error retrieving company by nit: {e}", exc_info=True, user_msg=f"No se pudo consultar la empresa. NIT {nit}")
            return None

    def find_by_name(self, name: str):
        try:
            row = self.session.query(CompanyModel).filter(CompanyModel.name.ilike(name.strip())).first()
            return (row.id, row.nit, row.name) if row else None
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error retrieving company by name: {e}", exc_info=True, user_msg=f"No se pudo consultar la empresa. Nombre {name}")
            return None

    def save(self, company):
        try:
            existing = self.find_by_name(company.name)
            if existing and existing[1] != company.nit:
                self.logger.warning(
                    f"Duplicate company name: {company.name} already exists with NIT {existing[1]}",
                    user_msg=f"Ya existe una empresa con el nombre '{company.name}' (NIT {existing[1]}).",
                )
                return None
            stmt = insert(CompanyModel).values(nit=company.nit, name=company.name, verified_at=func.now())
            stmt = stmt.on_conflict_do_update(
                index_elements=["nit"],
                set_={"name": stmt.excluded.name, "verified_at": stmt.excluded.verified_at},
            )
            stmt = stmt.returning(CompanyModel.id, CompanyModel.nit, CompanyModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving company: {e}", exc_info=True, user_msg=f"No se pudo guardar la empresa. {company.name}")
            return None

    def save_batch(self, companies):
        if not companies:
            return []
        try:
            existing_names = {
                row.name.strip().upper(): row.nit
                for row in self.session.query(CompanyModel.name, CompanyModel.nit).all()
            }
            filtered = []
            for c in companies:
                name_key = c.name.strip().upper()
                existing_nit = existing_names.get(name_key)
                if existing_nit and existing_nit != c.nit:
                    self.logger.warning(
                        f"Duplicate company name: {c.name} already exists with NIT {existing_nit}",
                        user_msg=f"Ya existe una empresa con el nombre '{c.name}' (NIT {existing_nit}). Se omite.",
                    )
                    continue
                filtered.append(c)
                existing_names[name_key] = c.nit
            if not filtered:
                return []
            stmt = insert(CompanyModel).values(
                [{"nit": c.nit, "name": c.name, "verified_at": func.now()} for c in filtered]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["nit"],
                set_={"name": stmt.excluded.name, "verified_at": stmt.excluded.verified_at},
            )
            stmt = stmt.returning(CompanyModel.id, CompanyModel.nit, CompanyModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch companies: {e}", exc_info=True, user_msg="No se pudieron guardar las empresas.")
            return None

    def all(self):
        try:
            rows = self.session.query(CompanyModel).all()
            return [{"id": r.id, "nit": r.nit, "name": r.name.upper()} for r in rows]
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error retrieving companies: {e}", exc_info=True, user_msg="No se pudo obtener el listado de empresas.")
            return None

    def companies_packages_all(self):
        try:
            rows = self.session.query(CompanyPackageModel).all()
            return [{"company": r.company_id, "package": r.package_id, "model": r.model} for r in rows]
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error searching companies_packages: {e}", exc_info=True, user_msg="No se pudo obtener las vinculaciones de empresas.")
            return None

    def companies_packages_batch(self, relations):
        """Batch upsert of CompanyPackage list."""
        if not relations:
            return
        try:
            stmt = insert(CompanyPackageModel).values([
                {"company_id": r.company_id, "package_id": r.package_id, "model": r.model}
                for r in relations
            ])
            stmt = stmt.on_conflict_do_update(
                index_elements=["company_id"],
                set_={"package_id": stmt.excluded.package_id, "model": stmt.excluded.model},
            )
            self.session.execute(stmt)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error batch saving companies_packages: {e}", exc_info=True, user_msg="No se pudieron vincular las empresas con los paquetes.")
