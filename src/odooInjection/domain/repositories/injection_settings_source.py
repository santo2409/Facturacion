from abc import ABC, abstractmethod
from pathlib import Path

from src.odooInjection.domain.entities.injection_settings import InjectionSettings


class InjectionSettingsSource(ABC):
    @abstractmethod
    def exists(self, path: Path) -> bool:
        """¿Existe el Excel de configuración?"""

    @abstractmethod
    def read(self, path: Path) -> InjectionSettings:
        """Lee el Excel. Lanza ValueError con un mensaje claro si falta una hoja o una columna."""

    @abstractmethod
    def create(self, path: Path, settings: InjectionSettings) -> None:
        """Crea el Excel con esos valores (primera vez)."""
