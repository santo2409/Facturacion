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
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller


def import_billers(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    session = get_session()

    use_case = ImportBillersFromExcel(
        biller_repo=SaBillerRepository(session, logger),
        company_repo=SaCompanyRepository(session, logger),
        biller_company_repo=SaBillerCompanyRepository(session, logger),
        nit_service=RUESNitService(logger),
        progress=RichProgress(),
        fuzz=RapidFuzzBiller(logger),
    )

    use_case.execute(df)
