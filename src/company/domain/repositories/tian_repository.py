from abc import ABC, abstractmethod


class TianRepository(ABC):
    @abstractmethod
    def all(self):
        """Retorna [{'nit_error','name'}], solo deleted_at IS NULL."""
        pass
