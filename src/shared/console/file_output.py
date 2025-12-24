from pathlib import Path

from rich.prompt import Prompt

from src.shared.utils.console import console


def ask_directory_path() -> Path:
    while True:
        path = Prompt.ask("Ruta completa en donde se va almacenar el libro")
        file = Path(path)

        if file.exists() and file.is_dir():
            return file

        console.print("Directorio inválido, intente de nuevo")
