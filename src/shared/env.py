"""Carga única del archivo .env (AUD-64).

Varios módulos necesitan el entorno al importarse (p. ej. database.py crea el
engine en ese momento), por eso cada uno llama a `load_env()` en su import; solo
la primera llamada del proceso lee el archivo. Precedencia igual que antes:
`override=True`, el .env gana sobre las variables ya definidas en el sistema.
"""

from dotenv import load_dotenv

_loaded = False


def load_env(dotenv_path=None) -> None:
    global _loaded
    if _loaded:
        return
    # Sin ruta, python-dotenv busca el .env subiendo desde este archivo: llega al
    # mismo .env de la raíz que encontraban las llamadas anteriores.
    load_dotenv(dotenv_path=dotenv_path, override=True)
    _loaded = True
