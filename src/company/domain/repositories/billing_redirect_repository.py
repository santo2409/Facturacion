from abc import ABC, abstractmethod


class BillingRedirectRepository(ABC):
    @abstractmethod
    def all(self):
        """Retorna [{'nit_origen','nit_destino','etiqueta','name'}], solo deleted_at IS NULL."""
        pass

    @abstractmethod
    def upsert_many(self, rows: list[dict]) -> tuple[int, int] | None:
        """Crea o actualiza (y reactiva) cada fila {'nit_origen','nit_destino','etiqueta','name'}.
        Devuelve (nuevas, actualizadas), o None si la escritura falló (no se guarda nada)."""
        pass

    @abstractmethod
    def deactivate(self, nits_origen: list[str]) -> list[str] | None:
        """Marca deleted_at en las filas activas de esos NIT. Devuelve los NIT desactivados, o None si falló."""
        pass
