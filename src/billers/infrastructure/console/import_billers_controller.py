from src.billers.application.use_cases.import_billers_from_excel import (
    ImportBillersFromExcel,
)
from src.billers.infrastructure.excel.excel_loader import ExcelLoader
from src.billers.infrastructure.external_services.nit_service import RUESNitService
from src.billers.infrastructure.persistence.mysql_biller_company_repository import (
    MySQLBillerCompanyRepository,
)
from src.billers.infrastructure.persistence.mysql_biller_repository import (
    MySQLBillerRepository,
)
from src.company.infrastructure.persistence.mysql_company_repository import (
    MySQLCompanyRepository,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.mysql_connection import get_connection
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller


def import_billers(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    conn = get_connection()

    use_case = ImportBillersFromExcel(
        biller_repo=MySQLBillerRepository(conn, logger),
        company_repo=MySQLCompanyRepository(conn, logger),
        biller_company_repo=MySQLBillerCompanyRepository(conn, logger),
        nit_service=RUESNitService(logger),
        progress=RichProgress(),
        fuzz=RapidFuzzBiller(conn, logger),
    )

    use_case.execute(df)
