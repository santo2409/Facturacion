from abc import ABC, abstractmethod

from src.scrapping.domain.entities.nit_result import NitResult


class NitScraperRepository(ABC):
    @abstractmethod
    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        pass
