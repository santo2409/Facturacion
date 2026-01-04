from src.activity.infrastructure.mysql_activity_type_repository import (
    MySQLActivityRepository,
)
from src.assign.application.use_cases.assigned_rates import AssignRatesFromExcel
from src.billers.infrastructure.persistence.mysql_biller_company_repository import (
    MySQLBillerCompanyRepository,
)
from src.billers.infrastructure.persistence.mysql_biller_repository import (
    MySQLBillerRepository,
)
from src.city.infrastructure.persistence.mysql_city_repository import (
    MySQLCityRepository,
)
from src.company.infrastructure.persistence.mysql_company_repository import (
    MySQLCompanyRepository,
)
from src.cup.infrastructure.persistence.mysql_cup_repository import MySQLCupRepository
from src.package.infrastructure.persistence.mysql_package_repository import (
    MySQLPackageRepository,
)
from src.provider.infrastructure.persistence.mysql_provider_repository import (
    MySQLProviderRepository,
)
from src.rates.infrastructure.persistence.mysql_rates_repository import (
    MySQLRatesRepository,
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


def assign_rates(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    conn = get_connection()

    use_case = AssignRatesFromExcel(
        biller_repo=MySQLBillerRepository(conn, logger),
        company_repo=MySQLCompanyRepository(conn, logger),
        biller_company_repo=MySQLBillerCompanyRepository(conn, logger),
        package_repo=MySQLPackageRepository(conn, logger),
        provider_repo=MySQLProviderRepository(conn, logger),
        special_repo=MySQLSpecialRepository(conn, logger),
        city_repo=MySQLCityRepository(conn, logger),
        activities_repo=MySQLActivityRepository(conn, logger),
        rates_repo=MySQLRatesRepository(conn, logger),
        cup_repo=MySQLCupRepository(),
        nit_service=RUESNitService(logger),
        fuzz=RapidFuzzBiller(conn, logger),
        progress=RichProgress(),
        logger=logger,
    )

    use_case.execute(df)
