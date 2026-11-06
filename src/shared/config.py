"""Configuración de rutas compartida por múltiples módulos.

Fuente única del valor por defecto de `DIRECTORY` (spec 007). Antes de este
módulo, cada consumidor llamaba `os.getenv("DIRECTORY")` por su cuenta: tres
sin ningún valor por defecto (TypeError si la variable falta) y dos con
valores por defecto distintos entre sí (`""` y `"."`). Ver specs/007.

Se usa `or` y no el segundo argumento de `os.getenv`, porque `.env.example`
trae `DIRECTORY=""`: quien copia la plantilla obtiene cadena vacía, no
ausencia, y `os.getenv("DIRECTORY", ".")` dejaría pasar esa cadena vacía sin
normalizarla.
"""

import os
from pathlib import Path

DEFAULT_DIRECTORY = "."

# Libro que escribe la opción 6 y lee la opción 7, relativo al directorio de trabajo.
CONSOLIDADO_PATH = Path("CONSOLIDADO.xlsx")


def get_paths_config() -> dict:
    return {"directory": os.getenv("DIRECTORY") or DEFAULT_DIRECTORY}


def get_tian_config() -> dict:
    """Config de facturación TIAN (spec 008).

    Sin valor por defecto deliberadamente (RF-19): un NIT de facturación
    asumido en silencio es justo el riesgo que se busca evitar. Si la
    variable falta, se devuelve cadena vacía y es responsabilidad de quien
    consuma esta config decidir abortar el tratamiento.
    """
    return {"nit": os.getenv("TIAN_NIT") or ""}


def get_book_config() -> dict:
    """Libro de NITs de la opción 1 (BOOK_ROUTE/BOOK_NAME).

    Sin valor por defecto: una variable ausente se devuelve como None y quien
    consume la config decide abortar con un mensaje claro. Una cadena vacía se
    conserva tal cual (BOOK_ROUTE="" equivale al directorio de trabajo).
    """
    return {"route": os.getenv("BOOK_ROUTE"), "name": os.getenv("BOOK_NAME")}


def get_int_env(name: str, default: int) -> int:
    """Entero desde una variable de entorno; `default` solo si la variable no existe.

    Una variable presente pero vacía o no numérica lanza ValueError (como el
    `int(os.getenv(...))` que reemplaza), con un mensaje que nombra la variable.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"La variable de entorno {name} debe ser un número entero.") from None
