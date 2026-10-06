from abc import ABC, abstractmethod

from src.scrapping.domain.entities.nit_result import NitResult


class NitCacheRepository(ABC):
    """Puerto para consultar/actualizar un caché de NITs ya resueltos como
    empresa válida. Solo debe usarse para POSITIVOS (is_company=True);
    los negativos se gestionan aparte (NotFoundCompaniesLogGenerator)."""

    @abstractmethod
    def get_many(self, nits: list[str]) -> dict[str, NitResult]:
        """Retorna solo los NITs encontrados en caché, indexados por NIT (str)."""

    @abstractmethod
    def get_by_names(self, names: list[str]) -> dict[str, NitResult]:
        """Retorna solo los nombres encontrados en caché, indexados por el
        nombre tal como lo pasó el llamador."""

    @abstractmethod
    def save_many(self, results: list[NitResult]) -> list[str]:
        """Persiste los resultados positivos (is_company=True) en el caché y
        retorna los NITs que NO pudieron persistirse, para que el llamador
        pueda reportarlos como novedad."""
