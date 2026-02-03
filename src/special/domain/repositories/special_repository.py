from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.special import Special


class SpecialRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[tuple]:
        pass

    @abstractmethod
    def save(self, special: Special) -> Optional[tuple]:
        pass

    @abstractmethod
    def update(self, special: Special) -> bool:
        pass

    @abstractmethod
    def all(self) -> Optional[List[dict]]:
        pass
