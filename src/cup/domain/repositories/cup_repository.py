from abc import ABC, abstractmethod


class CupRepository(ABC):
    @abstractmethod
    def exists(self, cup: str) -> bool:
        pass

    @abstractmethod
    def get_all_cups(self) -> list[str]:
        pass
