from src.package.domain.entities.package import Package
from src.package.domain.repositories.package_repository import PackageRepository
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class UpdatePackageUseCase:
    def __init__(self, package_repository: PackageRepository, logger: LoggerAdapter = None):
        self.package_repository = package_repository
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, package_id: int, name: str) -> bool:
        try:
            package = Package(name=name, id=package_id)
            return self.package_repository.update(package)
        except Exception as excep:
            self.logger.error(f"Error in update package use case: {excep}", exc_info=True)
            return False
