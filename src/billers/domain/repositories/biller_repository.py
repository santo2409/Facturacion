from abc import ABC, abstractmethod


class BillerRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str):
        pass

    @abstractmethod
    def save(self, biller):
        pass

    @abstractmethod
    def all(self):
        pass
