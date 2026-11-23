from abc import ABC, abstractmethod


class BillingRedirectRepository(ABC):
    @abstractmethod
    def all(self):
        """Retorna [{'nit_origen','nit_destino','etiqueta','name'}], solo deleted_at IS NULL."""
        pass
