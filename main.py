from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.assign.infrastructure.console.assigned_rates_controller import assign_rates
from src.billers.infrastructure.console.import_billers_controller import import_billers
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
from src.shared.logging.config.logging_config import setup_logging
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

console = Console()
user_logger = setup_logging()
tech_logger = LoggerAdapter("tech_logger")

load_dotenv(override=True)


def console_app():
    console.clear()
    console.rule("[bold blue]Facturación SOANDES")

    while True:
        console.print("\n[bold cyan]Menú Principal[/bold cyan]")
        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("Opción", justify="center")
        table.add_column("Descripción")

        table.add_row("1", "Web Scrapping")
        table.add_row("2", "Facturadores")
        table.add_row("3", "Tratamiento Información")
        table.add_row("4", "Cargar Tarifas")
        table.add_row("5", "Registrar Empresas - Paquetes")
        table.add_row("6", "Asignar Tarifas")
        table.add_row("0", "Salir")

        console.print(table)

        option = Prompt.ask("[bold yellow]Seleccione una opción", default="0")

        if option == "1":
            console.print("[green]Ejecutando Web Scrapping...[/green]")
            execute_web_scrapping()
        elif option == "2":
            console.print("[green]Cargando Facturadores...[/green]")
            import_billers(tech_logger)
        elif option == "3":
            console.print("[green]Validando y Organizando información...[/green]")
            import_information(tech_logger)
        elif option == "4":
            console.print("[green]Cargando Tarifas...[/green]")
            import_rates(tech_logger)
        elif option == "5":
            console.print("[green]Registrando Empresas...[/green]")
            import_companies(tech_logger)
        elif option == "6":
            console.print("[green]Asignando Tarifas...[/green]")
            assign_rates(tech_logger)
            generate_pre_invoices(tech_logger)
        elif option == "0":
            console.print("[red]Saliendo...[/red]")
            break
        else:
            console.print("[red]Opción inválida[/red]")


if __name__ == "__main__":
    console_app()
