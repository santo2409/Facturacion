from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.package.domain.entities.package import Package
from src.package.domain.repositories.package_repository import PackageRepository
from src.shared.database.models import PackageModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaPackageRepository(PackageRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(PackageModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as e:
            self.logger.error(f"Error finding package: {e}", exc_info=True, user_msg=f"No se pudo consultar el paquete. {name}")
            return None

    def save(self, package: Package):
        try:
            stmt = insert(PackageModel).values(name=package.name)
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(PackageModel.id, PackageModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving package: {e}", exc_info=True, user_msg=f"No se pudo guardar el paquete. {package.name}")
            return None

    def save_batch(self, packages: list[Package]):
        if not packages:
            return []
        try:
            stmt = insert(PackageModel).values([{"name": p.name} for p in packages])
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(PackageModel.id, PackageModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch packages: {e}", exc_info=True, user_msg="No se pudieron guardar los paquetes.")
            return []

    def update(self, package: Package) -> bool:
        try:
            if not package.id:
                return False
            obj = self.session.query(PackageModel).get(package.id)
            if not obj:
                return False
            obj.name = package.name
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error updating package: {e}", exc_info=True, user_msg="No se pudo actualizar el paquete.")
            return False

    def all(self):
        try:
            rows = self.session.query(PackageModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving packages: {e}", exc_info=True, user_msg="No se pudo obtener el listado de paquetes.")
            return None
