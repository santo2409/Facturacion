from pathlib import Path

from src.billers.infrastructure.persistence.sa_biller_company_repository import (
    SaBillerCompanyRepository,
)
from src.company.application.use_cases.import_billing_redirects_from_excel import (
    ImportBillingRedirectsFromExcel,
)
from src.company.infrastructure.persistence.sa_billing_redirect_repository import (
    SaBillingRedirectRepository,
)
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.company.infrastructure.persistence.sa_tian_repository import SaTianRepository
from src.shared.config import get_tian_config
from src.shared.console.file_input import ask_excel_path
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter


def import_billing_redirects(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)
    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    session = get_session()
    try:
        use_case = ImportBillingRedirectsFromExcel(
            redirect_repo=SaBillingRedirectRepository(session, logger),
            company_repo=SaCompanyRepository(session, logger),
            biller_company_repo=SaBillerCompanyRepository(session, logger),
            tian_repo=SaTianRepository(session, logger),
            findings_writer=XlsxFindingsWriter(Path("logs/redirecciones")),
            logger=logger,
            tian_nit=get_tian_config()["nit"],
        )
        return use_case.execute(df)
    finally:
        session.close()
