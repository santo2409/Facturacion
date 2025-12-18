from pathlib import Path

from rich.prompt import Prompt

from src.shared.utils.console import console


def ask_excel_path() -> Path:
    while True:
        path = Prompt.ask("Ruta completa del archivo Excel")
        file = Path(path)

        if file.exists() and file.suffix in (".xlsx", ".xls"):
            return file

        console.print("Archivo inválido, intente de nuevo")
