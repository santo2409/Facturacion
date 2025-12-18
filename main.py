import os

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.billers.infrastructure.console.import_billers_controller import import_billers
from src.scrapping.infrastructure.console.import_rues_nits import execute_web_scrapping
from src.shared.logging.config.logging_config import setup_logging

console = Console()
logger = setup_logging()

load_dotenv(override=True)


def console_app():
    console.clear()
    console.rule("[bold blue]Facturación SOANDES")

    destiny = os.getenv("BOOK_DESTINY", "")

    while True:
        console.print("\n[bold cyan]Menú Principal[/bold cyan]")
        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("Opción", justify="center")
        table.add_column("Descripción")

        table.add_row("1", "Cargar Tarifas Especiales")
        table.add_row("2", "Cargar Tarifas Paquetes")
        table.add_row("3", "Cargar Tarifas Proveedores")
        table.add_row("4", "Registrar Empresas - Paquetes")
        table.add_row("5", "Facturadores")
        table.add_row("6", "Tratamiento Información")
        table.add_row("7", "Web Scrapping")
        table.add_row("0", "Salir")

        console.print(table)

        option = Prompt.ask("[bold yellow]Seleccione una opción", default="0")

        if option == "1":
            console.print("[green]Cargando Tarifas Especiales...[/green]")
            # insert_rates_specials()
        elif option == "2":
            console.print("[green]Cargando Tarifas Especiales...[/green]")
            # insert_rates_packages()
        elif option == "3":
            console.print("[green]Cargando Tarifas Especiales...[/green]")
            # insert_rates_providers()
        elif option == "4":
            console.print("[green]Registrando Empresas...[/green]")
        elif option == "5":
            console.print("[green]Cargando Facturadores...[/green]")
            import_billers(logger)
        elif option == "6":
            console.print("[green]Cargando Tarifas Especiales...[/green]")
            console.print("[green]Información exportada[/green]")
        elif option == "7":
            console.print("[green]Ejecutando Web Scrapping...[/green]")
            execute_web_scrapping()
        elif option == "0":
            console.print("[red]Saliendo...[/red]")
            break
        else:
            console.print("[red]Opción inválida[/red]")


if __name__ == "__main__":
    console_app()
