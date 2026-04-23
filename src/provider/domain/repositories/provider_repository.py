from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.provider import Provider


class ProviderRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[tuple]:
        pass

    @abstractmethod
    def save(self, provider: Provider) -> Optional[tuple]:
        pass

    @abstractmethod
    def save_batch(self, providers: list) -> list:
        pass

    @abstractmethod
    def update(self, provider: Provider) -> bool:
        pass

    @abstractmethod
    def all(self) -> Optional[List[dict]]:
        pass
