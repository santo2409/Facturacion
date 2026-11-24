"""Opción 5 del menú: Cargar Pre Facturas (integración de ETL-Avancys).

Raíz de composición: valida la configuración de Odoo, lee el Excel de configuración
(lo crea con los valores del ETL la primera vez), pide la carpeta de pre-facturas y
ejecuta el caso de uso. No usa la BD local.
"""

from datetime import datetime
from pathlib import Path

from src.odooInjection.application.use_cases.load_pre_invoices_to_odoo import (
    LoadPreInvoicesToOdoo,
)
from src.odooInjection.config import get_injection_config, get_odoo_config
from src.odooInjection.domain.entities.injection_settings import valores_del_etl
from src.odooInjection.infrastructure.odoo.xmlrpc_injection_gateway import (
    XmlRpcInjectionGateway,
)
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.odooInjection.infrastructure.persistence.xlsx_injection_settings_source import (
    XlsxInjectionSettingsSource,
)
from src.odooInjection.infrastructure.persistence.xlsx_pre_invoice_source import (
    XlsxPreInvoiceSource,
)
from src.odooInjection.infrastructure.reporting.etl_injection_report_writer import (
    EtlInjectionReportWriter,
)
from src.shared.console.file_input import ask_folder_path
from src.shared.console.progress import RichProgress


def load_pre_invoices(logger):
    odoo = get_odoo_config()
    faltan = [n for n, k in (("ODOO_URL", "url"), ("ODOO_DB", "db"),
                             ("ODOO_USERNAME", "username"), ("ODOO_API_KEY", "api_key"))
              if not odoo[k]]
    if faltan:
        logger.error(
            "Configuración de Odoo incompleta: " + ", ".join(faltan),
            user_msg="Faltan variables de Odoo en el .env: " + ", ".join(faltan) + ".",
        )
        return None

    cfg = get_injection_config()
    settings_source = XlsxInjectionSettingsSource()
    config_path = Path(cfg["config_xlsx"])
    if not settings_source.exists(config_path):
        settings_source.create(config_path, valores_del_etl())
        logger.warning(
            f"Se creó {config_path} con los valores de ETL-Avancys",
            user_msg=(f"Se creó {config_path} con los bloqueos actuales del ETL. "
                      "Revísalo (sobre todo YA_SUBIDAS, que debe estar vacío cada mes) "
                      "y vuelve a ejecutar la opción."),
        )
        return None
    try:
        settings = settings_source.read(config_path)
    except ValueError as e:
        logger.error(str(e), user_msg=str(e))
        return None

    input_dir = ask_folder_path("Ruta de la carpeta con las pre-facturas a cargar")
    output_dir = Path(cfg["salida"]) / datetime.now().strftime("%Y-%m-%d_%H%M")

    repo = XmlRpcOdooRepository(
        url=odoo["url"], db=odoo["db"], username=odoo["username"],
        api_key=odoo["api_key"], logger=logger, config=odoo,
    )
    use_case = LoadPreInvoicesToOdoo(
        gateway=XmlRpcInjectionGateway(repo, odoo["url"], odoo["db"], odoo["api_key"]),
        source=XlsxPreInvoiceSource(logger),
        settings=settings,
        writer=EtlInjectionReportWriter(output_dir, logger),
        logger=logger,
        config={**odoo, **cfg},
        progress=RichProgress(),
    )
    resumen = use_case.execute(input_dir)
    if resumen is not None:
        logger.info(f"Salidas en {output_dir}", user_msg=f"Libros de la corrida en {output_dir}")
    return resumen
