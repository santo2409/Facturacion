from abc import ABC, abstractmethod


class ImedicalRepository(ABC):
    @abstractmethod
    def all(self):
        """Retorna [{'nit_error','name','nit_success','name_error'}], solo deleted_at IS NULL."""
        pass

    @abstractmethod
    def save_batch(self, corrections: list):
        """Upsert por nit_error. Retorna el número de filas escritas."""
        pass
