from collections.abc import Callable
from datetime import datetime
from os import getenv

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.assign.infrastructure.console.assigned_rates_controller import assign_rates
from src.assign.infrastructure.console.missing_rates_controller import (
    generate_missing_rates,
)
from src.billers.infrastructure.console.import_billers_controller import import_billers
from src.company.infrastructure.console.detect_duplicates_controller import (
    detect_duplicate_companies,
)
from src.company.infrastructure.console.import_companies_rates_controller import (
    import_companies,
)
from src.dataProcessing.infrastructure.console.import_information_controller import (
    import_information,
)
from src.preInvoice.infrastructure.console.pre_invoice_controller import (
    generate_pre_invoices,
)
from src.rates.infrastructure.console.import_rates_controller import import_rates
from src.scrapping.infrastructure.console.import_rues_nits import execute_web_scrapping
from src.shared.env import load_env
from src.shared.logging.config.logging_config import setup_logging
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.deprecated import DEPRECATED_LABEL, is_deprecated

console = Console()
user_logger = setup_logging()
tech_logger = LoggerAdapter("tech_logger")

load_env()

# (opción, descripción, función). La función sirve para detectar @deprecated;
# None cuando la opción no tiene controller (Salir) o está desconectada (8).
MENU_OPTIONS: list[tuple[str, str, Callable | None]] = [
    ("1", "Web Scrapping", execute_web_scrapping),
    ("2", "Facturadores", import_billers),
    ("3", "Tratamiento Información", import_information),
    ("4", "Cargar Tarifas", import_rates),
    ("5", "Registrar Empresas - Paquetes", import_companies),
    ("6", "Asignar Tarifas", assign_rates),
    ("7", "Generar Pre Facturas", generate_pre_invoices),
    ("8", "Cargar Pre Facturas", None),
    ("9", "Generar Faltantes", generate_missing_rates),
    ("10", "Detectar Empresas Duplicadas", detect_duplicate_companies),
    ("0", "Salir", None),
]


def menu_label(description: str, func: Callable | None) -> str:
    if is_deprecated(func):
        return f"{description} {DEPRECATED_LABEL}"
    return description


def dispatch_option(option, logger) -> bool:
    if option == "1":
        console.print("[green]Ejecutando Web Scrapping...[/green]")
        execute_web_scrapping(logger)
    elif option == "2":
        console.print("[green]Cargando Facturadores...[/green]")
        import_billers(logger)
    elif option == "3":
        console.print("[green]Validando y Organizando información...[/green]")
        import_information(logger)
    elif option == "4":
        console.print("[green]Cargando Tarifas...[/green]")
        import_rates(logger)
    elif option == "5":
        console.print("[green]Registrando Empresas...[/green]")
        import_companies(logger)
    elif option == "6":
        console.print("[green]Asignando Tarifas...[/green]")
        day = datetime.now().day
        should_generate = day < int(getenv("DAY_INITIAL")) or day > int(
            getenv("DAY_FINAL")
        )
        assign_rates(logger, with_invoices=should_generate)
    elif option == "7":
        console.print("[green]Generando Pre Facturas...[/green]")
        generate_pre_invoices(logger)
    elif option == "8":
        console.print("[green]Inyectando Facturas...[/green]")
        # inject_invoices(logger)
    elif option == "9":
        console.print("[green]Generando Faltantes...[/green]")
        generate_missing_rates(logger)
    elif option == "10":
        console.print("[green]Detectando Empresas Duplicadas...[/green]")
        detect_duplicate_companies(logger)
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
    for option, description, func in MENU_OPTIONS:
        table.add_row(option, menu_label(description, func))
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
