from src.company.application.use_cases.import_companies_from_excel import (
    ImportCompaniesFromExcel,
)
from src.company.infrastructure.persistence.mysql_company_repository import (
    MySQLCompanyRepository,
)
from src.package.infrastructure.persistence.mysql_package_repository import (
    MySQLPackageRepository,
)
from src.provider.infrastructure.persistence.mysql_provider_repository import (
    MySQLProviderRepository,
)
from src.scrapping.infrastructure.console.nit_service import RUESNitService
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.database.mysql_connection import get_connection
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.mysql_special_repository import (
    MySQLSpecialRepository,
)


def import_companies(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    conn = get_connection()

    use_case = ImportCompaniesFromExcel(
        company_repo=MySQLCompanyRepository(conn, logger),
        package_repo=MySQLPackageRepository(conn, logger),
        provider_repo=MySQLProviderRepository(conn, logger),
        special_repo=MySQLSpecialRepository(conn, logger),
        fuzz=RapidFuzzBiller(conn, logger),
        nit_service=RUESNitService(logger),
        progress=RichProgress(),
        logger=logger,
    )

    use_case.execute(df)
