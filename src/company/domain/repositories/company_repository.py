from abc import ABC, abstractmethod


class CompanyRepository(ABC):
    @abstractmethod
    def find_by_nit(self, nit: str):
        pass

    @abstractmethod
    def save(self, company):
        pass

    @abstractmethod
    def save_batch(self, companies: list):
        pass

    @abstractmethod
    def find_by_name(self, name: str):
        pass

    @abstractmethod
    def all(self):
        pass

    @abstractmethod
    def companies_packages_all(self):
        pass

    @abstractmethod
    def companies_packages_batch(self, relations: list):
        pass
