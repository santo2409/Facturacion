from abc import ABC, abstractmethod


class BillerCompanyRepository(ABC):
    @abstractmethod
    def link(self, company_id: int, biller_id: int):
        pass
