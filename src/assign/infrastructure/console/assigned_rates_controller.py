import polars as pl

from src.activity.infrastructure.sa_activity_type_repository import (
    SaActivityRepository,
)
from src.assign.application.use_cases.assigned_rates import AssignRatesFromExcel
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
from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository
from src.package.infrastructure.persistence.sa_package_repository import (
    SaPackageRepository,
)
from src.provider.infrastructure.persistence.sa_provider_repository import (
    SaProviderRepository,
)
from src.rates.infrastructure.persistence.sa_rates_repository import (
    SaRatesRepository,
)
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.sa_special_repository import (
    SaSpecialRepository,
)


def assign_rates(logger, with_invoices=False):
    loader = ExcelLoader()

    # Libro consolidado (tarifas)
    path = ask_excel_path()
    excel = loader.load(path)
    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    # Libro de facturas (solo si se generarán pre-facturas)
    if with_invoices:
        facture_path = ask_excel_path()
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
        nit_service=RUESNitService(logger),
        fuzz=RapidFuzzBiller(logger),
        progress=RichProgress(),
        logger=logger,
    )

    use_case.execute(df, df_facture)
