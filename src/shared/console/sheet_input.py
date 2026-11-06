from rich.prompt import Prompt

from src.shared.utils.console import console


def ask_sheet_name(sheets: list[str]) -> str:
    console.print("Hojas disponibles:")

    for s in sheets:
        console.print(f" - {s}", markup=False, highlight=False)

    return Prompt.ask("Nombre de la hoja a procesar")
