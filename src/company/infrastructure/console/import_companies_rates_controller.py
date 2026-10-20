from pathlib import Path

from src.company.application.use_cases.import_companies_from_excel import (
    ImportCompaniesFromExcel,
)
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.company.infrastructure.reporting.not_linked_companies_log_generator import (
    NotLinkedCompaniesLogGenerator,
)
from src.package.infrastructure.persistence.sa_package_repository import (
    SaPackageRepository,
)
from src.odooInjection.config import get_odoo_config
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.provider.infrastructure.persistence.sa_provider_repository import (
    SaProviderRepository,
)
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from src.scrapping.infrastructure.reporting.not_found_companies_log_generator import (
    NotFoundCompaniesLogGenerator,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.sa_special_repository import (
    SaSpecialRepository,
)
from src.shared.utils.deprecated import deprecated


def _load_dataframe():
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)
    sheet = ask_sheet_name(excel.sheet_names)
    return loader.load_sheet(excel, sheet)


def _build_use_case(session, logger) -> ImportCompaniesFromExcel:
    company_repo = SaCompanyRepository(session, logger)

    config = get_odoo_config()
    odoo_repo = None
    if config["username"] and config["api_key"]:
        odoo_repo = XmlRpcOdooRepository(
            url=config["url"],
            db=config["db"],
            username=config["username"],
            api_key=config["api_key"],
            logger=logger,
            config=config,
        )
    nit_cache_repo = SaCompanyNitCacheRepository(company_repo, logger=logger)

    return ImportCompaniesFromExcel(
        company_repo=company_repo,
        package_repo=SaPackageRepository(session, logger),
        provider_repo=SaProviderRepository(session, logger),
        special_repo=SaSpecialRepository(session, logger),
        fuzz=RapidFuzzBiller(logger),
        nit_service=RUESNitService(logger, odoo_repo=odoo_repo, nit_cache_repo=nit_cache_repo),
        progress=RichProgress(),
        logger=logger,
        not_found_log_generator=NotFoundCompaniesLogGenerator(logger),
        logs_dir=Path("logs"),
        not_linked_log_generator=NotLinkedCompaniesLogGenerator(logger),
        findings_writer=XlsxFindingsWriter(Path("logs/registrar_empresas")),
        rues_cache_loader=load_rues_cache,
    )


@deprecated("Opción en desuso del menú")
def import_companies(logger):
    df = _load_dataframe()

    session = get_session()
    try:
        use_case = _build_use_case(session, logger)
        use_case.execute(df)
    except Exception as e:
        logger.error(
            f"Error registrando empresas: {e}",
            exc_info=True,
            user_msg="Ocurrió un error al registrar las empresas.",
        )
    finally:
        session.close()
