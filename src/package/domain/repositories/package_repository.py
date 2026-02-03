from abc import ABC, abstractmethod
from typing import List, Optional

from src.package.domain.entities.package import Package


class PackageRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[tuple]:
        pass

    @abstractmethod
    def save(self, package: Package) -> Optional[tuple]:
        pass

    @abstractmethod
    def update(self, package: Package) -> bool:
        pass

    @abstractmethod
    def all(self) -> Optional[List[dict]]:
        pass
