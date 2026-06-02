from pathlib import Path

from src.odooInjection.application.use_cases.inject_invoices_to_odoo import (
    InjectInvoicesToOdoo,
)
from src.odooInjection.config import get_odoo_config
from src.odooInjection.domain.services.city_account_resolver import CityAccountResolver
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.odooInjection.infrastructure.persistence.excel_pre_invoice_reader import (
    ExcelPreInvoiceReader,
)
from src.odooInjection.infrastructure.reporting.excel_log_generator import (
    ExcelLogGenerator,
)
from src.shared.console.progress import RichProgress

INPUT_DIR = Path("pre-facturas/General sin factura")
OUTPUT_DIR = Path("odoo-output")


def inject_invoices(logger):
    config = get_odoo_config()

    if not config["username"] or not config["api_key"]:
        logger.error(
            "Credenciales Odoo no configuradas (ODOO_USERNAME, ODOO_API_KEY)",
            user_msg="Configura las credenciales de Odoo en el archivo .env",
        )
        return

    odoo_repo = XmlRpcOdooRepository(
        url=config["url"],
        db=config["db"],
        username=config["username"],
        api_key=config["api_key"],
        logger=logger,
        config=config,
    )

    use_case = InjectInvoicesToOdoo(
        odoo_repo=odoo_repo,
        reader_repo=ExcelPreInvoiceReader(logger),
        city_resolver=CityAccountResolver(),
        log_generator=ExcelLogGenerator(logger),
        progress=RichProgress(),
        logger=logger,
        config=config,
    )

    use_case.execute(INPUT_DIR, OUTPUT_DIR)
