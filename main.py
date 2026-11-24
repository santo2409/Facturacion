from datetime import datetime
from os import getenv

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.assign.infrastructure.console.assigned_rates_controller import assign_rates
from src.billers.infrastructure.console.import_billers_controller import import_billers
from src.odooInjection.infrastructure.console.load_pre_invoices_controller import (
    load_pre_invoices,
)
from src.preInvoice.infrastructure.console.pre_invoice_controller import (
    generate_pre_invoices,
)
from src.scrapping.infrastructure.console.import_rues_nits import execute_web_scrapping
from src.shared.env import load_env
from src.shared.logging.config.logging_config import setup_logging
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

console = Console()
user_logger = setup_logging()
tech_logger = LoggerAdapter("tech_logger")

load_env()

# (opción, descripción). La opción 5 es la integración de ETL-Avancys.
MENU_OPTIONS: list[tuple[str, str]] = [
    ("1", "Web Scrapping"),
    ("2", "Facturadores"),
    ("3", "Asignar Tarifas"),
    ("4", "Generar Pre Facturas"),
    ("5", "Cargar Pre Facturas"),
    ("0", "Salir"),
]


def dispatch_option(option, logger) -> bool:
    if option == "1":
        console.print("[green]Ejecutando Web Scrapping...[/green]")
        execute_web_scrapping(logger)
    elif option == "2":
        console.print("[green]Cargando Facturadores...[/green]")
        import_billers(logger)
    elif option == "3":
        console.print("[green]Asignando Tarifas...[/green]")
        day = datetime.now().day
        should_generate = day < int(getenv("DAY_INITIAL")) or day > int(
            getenv("DAY_FINAL")
        )
        assign_rates(logger, with_invoices=should_generate)
    elif option == "4":
        console.print("[green]Generando Pre Facturas...[/green]")
        generate_pre_invoices(logger)
    elif option == "5":
        console.print("[green]Cargando Pre Facturas en Odoo...[/green]")
        load_pre_invoices(logger)
    elif option == "0":
        console.print("[red]Saliendo...[/red]")
        return False
    else:
        console.print("[red]Opción inválida[/red]")
    return True


def safe_dispatch(option, logger) -> bool:
    """RF-09: contiene cualquier excepción no controlada de una opción del
    menú. El menú continúa (retorna True) en vez de terminar el proceso."""
    try:
        return dispatch_option(option, logger)
    except Exception as e:
        logger.error(
            f"Error ejecutando la opción {option}: {e}",
            exc_info=True,
            user_msg="Ocurrió un error ejecutando la opción seleccionada.",
        )
        console.print(
            "[red]Ocurrió un error ejecutando la opción. Revisa los logs.[/red]"
        )
        return True


def build_menu_table() -> Table:
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Opción", justify="center")
    table.add_column("Descripción")
    for option, description in MENU_OPTIONS:
        table.add_row(option, description)
    return table


def console_app():
    console.clear()
    console.rule("[bold blue]Facturación SOANDES")

    while True:
        console.print("\n[bold cyan]Menú Principal[/bold cyan]")
        console.print(build_menu_table())

        option = Prompt.ask("[bold yellow]Seleccione una opción", default="0")

        if not safe_dispatch(option, tech_logger):
            break


if __name__ == "__main__":
    console_app()
