from abc import ABC, abstractmethod


class BillerCompanyRepository(ABC):
    @abstractmethod
    def link_or_update_batch(self, pairs: list):
        pass

    @abstractmethod
    def all(self):
        pass
