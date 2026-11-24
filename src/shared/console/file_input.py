from pathlib import Path

from rich.prompt import Prompt

from src.shared.utils.console import console


def ask_excel_path(label: str = "Ruta completa del archivo Excel") -> Path:
    while True:
        path = Prompt.ask(label)
        file = Path(path)

        if file.exists() and file.suffix in (".xlsx", ".xls"):
            return file

        console.print("Archivo inválido, intente de nuevo")


def ask_folder_path(label: str = "Ruta completa de la carpeta") -> Path:
    while True:
        folder = Path(Prompt.ask(label).strip().strip('"'))

        if folder.is_dir():
            return folder

        console.print("Carpeta inválida, intente de nuevo")
