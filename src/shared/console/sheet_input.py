from rich.prompt import Prompt

from src.shared.utils.console import console


def ask_sheet_name(sheets: list[str]) -> str:
    console.print("Hojas disponibles:")

    for s in sheets:
        print(f" - {s}")

    return Prompt.ask("Nombre de la hoja a procesar")
