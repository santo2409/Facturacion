from pathlib import Path

from src.billers.application.use_cases.import_billers_from_excel import (
    ImportBillersFromExcel,
)
from src.billers.infrastructure.persistence.sa_biller_company_repository import (
    SaBillerCompanyRepository,
)
from src.billers.infrastructure.persistence.sa_biller_repository import (
    SaBillerRepository,
)
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.odooInjection.config import get_odoo_config
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller


def _build_use_case(session, logger):
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

    return ImportBillersFromExcel(
        biller_repo=SaBillerRepository(session, logger),
        company_repo=company_repo,
        biller_company_repo=SaBillerCompanyRepository(session, logger),
        nit_service=RUESNitService(logger, odoo_repo=odoo_repo, nit_cache_repo=nit_cache_repo),
        progress=RichProgress(),
        fuzz=RapidFuzzBiller(logger),
        logger=logger,
        findings_writer=XlsxFindingsWriter(Path("logs/facturadores")),
        rues_cache_loader=load_rues_cache,
    )


def import_billers(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    session = get_session()
    try:
        use_case = _build_use_case(session, logger)
        use_case.execute(df)
    finally:
        session.close()
