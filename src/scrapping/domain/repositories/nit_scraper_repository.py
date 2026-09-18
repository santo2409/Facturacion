from abc import ABC, abstractmethod

from src.scrapping.domain.entities.nit_result import NitResult


class NitScraperRepository(ABC):
    @abstractmethod
    def search_nits(self, nits: list, show_progress: bool = False) -> list[NitResult]:
        pass

    @abstractmethod
    def search_by_name(self, name: str) -> NitResult | None:
        pass

    def search_names(
        self, names: list[str], show_progress: bool = False
    ) -> dict[str, NitResult]:
        """Resuelve varios nombres en lote, omitiendo los que no se encuentran.

        Es concreto y no abstracto a propósito: los adaptadores cuyo coste por
        consulta sea alto deben sobreescribirlo para reutilizar recursos, pero
        los que no lo hagan siguen funcionando con esta implementación.
        """
        found: dict[str, NitResult] = {}
        for name in names:
            result = self.search_by_name(name)
            if result:
                found[name] = result
        return found
