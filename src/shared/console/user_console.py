from rich.console import Console
from rich.logging import RichHandler

# Una única consola para barras de progreso y mensajes de usuario: con la misma
# instancia, Rich imprime los mensajes por encima de la barra sin romperla.
USER_CONSOLE = Console()


def build_user_console_handler() -> RichHandler:
    return RichHandler(console=USER_CONSOLE, show_time=False, show_path=False, markup=False)
