from pathlib import Path

import polars as pl
from rich.console import Console
from rich.table import Table

from src.activity.infrastructure.sa_activity_type_repository import (
    SaActivityRepository,
)
from src.assign.application.use_cases.assigned_rates import (
    AssignRatesFromExcel,
    AssignRatesResult,
)
from src.assign.infrastructure.reporting.xlsx_phase_findings_reporter import (
    XlsxPhaseFindingsReporter,
)
from src.billers.infrastructure.persistence.sa_biller_company_repository import (
    SaBillerCompanyRepository,
)
from src.billers.infrastructure.persistence.sa_biller_repository import (
    SaBillerRepository,
)
from src.city.infrastructure.persistence.sa_city_repository import (
    SaCityRepository,
)
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.company.infrastructure.persistence.sa_imedical_repository import (
    SaImedicalRepository,
)
from src.company.infrastructure.persistence.sa_tian_repository import (
    SaTianRepository,
)
from src.company.infrastructure.reporting.tian_companies_log_generator import (
    TianCompaniesLogGenerator,
)
from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository
from src.odooInjection.config import get_odoo_config
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.package.infrastructure.persistence.sa_package_repository import (
    SaPackageRepository,
)
from src.provider.infrastructure.persistence.sa_provider_repository import (
    SaProviderRepository,
)
from src.rates.infrastructure.persistence.sa_rates_repository import (
    SaRatesRepository,
)
from src.scrapping.infrastructure.reporting.not_found_companies_log_generator import (
    NotFoundCompaniesLogGenerator,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.logging.infrastructure.logging.tech_only_logger import TechOnlyLogger
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.sa_special_repository import (
    SaSpecialRepository,
)


_SUMMARY_LABELS = {
    "odoo": "Tarifa Odoo (especial/base)",
    "fase_01_paquete_propio_local": "Fase 1 — Paquete propio local",
    "fase_02_paquete_c_2025": "Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)",
    "fase_03_cualquier_paquete": "Fase 3 — Cualquier paquete (mismo CUP, misma ciudad)",
    "fase_04_cup_base_paquete_c": "Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)",
    "fase_05_cup_base_cualquier_paquete": "Fase 5 — Cualquier paquete (CUP base, misma ciudad)",
    "fase_06_cualquier_ciudad": "Fase 6 — Cualquier paquete/ciudad (cup + actividad)",
    "sin_resolver": "Sin resolver (valor 1)",
}


def render_summary(result: AssignRatesResult) -> Table:
    caption = (
        f"Hallazgos por fase en: {result.findings_dir}"
        if result.findings_dir
        else "Sin hallazgos: no se generaron libros por fase."
    )
    if not result.odoo_available:
        caption += "\n[yellow]Odoo no disponible: todas las tarifas salieron de la cascada local.[/yellow]"
    table = Table(title="Asignación de tarifas", caption=caption)
    table.add_column("Origen del precio")
    table.add_column("Celdas", justify="right")
    for key, label in _SUMMARY_LABELS.items():
        table.add_row(label, str(result.counts.get(key, 0)))
    return table


def assign_rates(logger, with_invoices=False):
    loader = ExcelLoader()

    # Libro consolidado (tarifas)
    path = ask_excel_path("Ruta del Excel de TARIFAS (consolidado)")
    excel = loader.load(path)
    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    # Libro de facturas (solo si se generarán pre-facturas)
    if with_invoices:
        facture_path = ask_excel_path("Ruta del Excel con NÚMEROS DE FACTURA")
        facture_excel = loader.load(facture_path)
        facture_sheet = ask_sheet_name(facture_excel.sheet_names)
        df_facture = loader.load_sheet(facture_excel, facture_sheet)

        missing = [c for c in ("N° Identificación", "# FACTURA") if c not in df_facture.columns]
        if missing:
            logger.error(f"Columnas faltantes en libro de facturas: {missing}")
            raise ValueError(f"Columnas faltantes en libro de facturas: {missing}")
    else:
        df_facture = pl.DataFrame({"N° Identificación": [], "# FACTURA": []})

    session = get_session()
    config = get_odoo_config()
    odoo_repo = XmlRpcOdooRepository(
        url=config["url"],
        db=config["db"],
        username=config["username"],
        api_key=config["api_key"],
        logger=logger,
        config=config,
    )

    use_case = AssignRatesFromExcel(
        biller_repo=SaBillerRepository(session, logger),
        company_repo=SaCompanyRepository(session, logger),
        biller_company_repo=SaBillerCompanyRepository(session, logger),
        package_repo=SaPackageRepository(session, logger),
        provider_repo=SaProviderRepository(session, logger),
        special_repo=SaSpecialRepository(session, logger),
        city_repo=SaCityRepository(session, logger),
        activities_repo=SaActivityRepository(session, logger),
        rates_repo=SaRatesRepository(session, logger),
        cup_repo=SaCupRepository(session),
        fuzz=RapidFuzzBiller(logger),
        progress=RichProgress(),
        logger=logger,
        odoo_repo=odoo_repo,
        not_found_log_generator=NotFoundCompaniesLogGenerator(logger),
        logs_dir=Path("logs"),
        imedical_repo=SaImedicalRepository(session, logger),
        tian_repo=SaTianRepository(session, logger),
        tian_log_generator=TianCompaniesLogGenerator(logger),
    )

    use_case.execute(df, df_facture)
