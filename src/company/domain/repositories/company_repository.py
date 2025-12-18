from abc import ABC, abstractmethod


class CompanyRepository(ABC):
    @abstractmethod
    def find_by_nit(self, nit: str):
        pass

    @abstractmethod
    def save(self, company):
        pass

    @abstractmethod
    def all(self):
        pass
