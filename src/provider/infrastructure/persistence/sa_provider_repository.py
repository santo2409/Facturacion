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
        except Exception as excep:
            self.logger.error(
                f"Error finding provider by name: {excep}",
                exc_info=True,
                user_msg=f"No se pudo consultar el proveedor. {name}",
            )
            return None

    def save(self, provider):
        try:
            exists = self.find_by_name(provider.name)
            if exists:
                obj = self.session.query(ProviderModel).get(exists[0])
                obj.name = provider.name
                self.session.commit()
                return Provider(id=obj.id, name=obj.name)

            obj = ProviderModel(name=provider.name)
            self.session.add(obj)
            self.session.commit()
            return (obj.id, obj.name)
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error saving provider: {excep}",
                exc_info=True,
                user_msg=f"No se pudo guardar el proveedor. {provider.name}",
            )
            return None

    def update(self, provider: Provider) -> bool:
        try:
            if not provider.id:
                self.logger.error("Provider ID is required for update", user_msg="No se puede actualizar sin identificador.")
                return False
            obj = self.session.query(ProviderModel).get(provider.id)
            if not obj:
                return False
            obj.name = provider.name
            self.session.commit()
            return True
        except Exception as excep:
            self.session.rollback()
            self.logger.error(
                f"Error updating provider: {excep}",
                exc_info=True,
                user_msg="No se pudo actualizar el proveedor.",
            )
            return False

    def all(self):
        try:
            rows = self.session.query(ProviderModel).all()
            return [{"id": r.id, "name": r.name} for r in rows]
        except Exception as excep:
            self.logger.error(
                f"Error retrieving all rates providers: {excep}",
                exc_info=True,
                user_msg="No se pudo obtener el listado de proveedores.",
            )
            return None
