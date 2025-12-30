from abc import ABC, abstractmethod


class ImportBillerFromExcelRepository(ABC):
    @abstractmethod
    def __init__(self, *args):
        pass

    @abstractmethod
    def execute(self, df):
        pass

    @abstractmethod
    def _process_billers(self, df):
        pass

    @abstractmethod
    def _process_companies(self, df):
        pass
