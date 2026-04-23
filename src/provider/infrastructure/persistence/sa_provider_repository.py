from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.provider.domain.entities.provider import Provider
from src.provider.domain.repositories.provider_repository import ProviderRepository
from src.shared.database.models import ProviderModel
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class SaProviderRepository(ProviderRepository):
    def __init__(self, session: Session, logger: LoggerAdapter = None):
        self.session = session
        self.logger = logger or LoggerAdapter(__name__)

    def find_by_name(self, name):
        try:
            row = self.session.query(ProviderModel).filter_by(name=name).first()
            return (row.id, row.name) if row else None
        except Exception as e:
            self.logger.error(f"Error finding provider: {e}", exc_info=True, user_msg=f"No se pudo consultar el proveedor. {name}")
            return None

    def save(self, provider: Provider):
        try:
            stmt = insert(ProviderModel).values(name=provider.name)
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(ProviderModel.id, ProviderModel.name)
            row = self.session.execute(stmt).fetchone()
            self.session.commit()
            return row
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving provider: {e}", exc_info=True, user_msg=f"No se pudo guardar el proveedor. {provider.name}")
            return None

    def save_batch(self, providers: list[Provider]):
        if not providers:
            return []
        try:
            stmt = insert(ProviderModel).values([{"name": p.name} for p in providers])
            stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"name": stmt.excluded.name})
            stmt = stmt.returning(ProviderModel.id, ProviderModel.name)
            rows = self.session.execute(stmt).fetchall()
            self.session.commit()
            return rows
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error saving batch providers: {e}", exc_info=True, user_msg="No se pudieron guardar los proveedores.")
            return []

    def update(self, provider: Provider) -> bool:
        try:
            if not provider.id:
                return False
            obj = self.session.query(ProviderModel).get(provider.id)
            if not obj:
                return False
            obj.name = provider.name
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error updating provider: {e}", exc_info=True, user_msg="No se pudo actualizar el proveedor.")
            return False

    def all(self):
        try:
            rows = self.session.query(ProviderModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving providers: {e}", exc_info=True, user_msg="No se pudo obtener el listado de proveedores.")
            return None
