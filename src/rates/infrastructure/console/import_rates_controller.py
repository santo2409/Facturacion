from src.activity.infrastructure.mysql_activity_type_repository import (
    MySQLActivityRepository,
)
from src.city.infrastructure.persistence.mysql_city_repository import (
    MySQLCityRepository,
)
from src.cup.infrastructure.persistence.mysql_cup_repository import MySQLCupRepository
from src.package.infrastructure.persistence.mysql_package_repository import (
    MySQLPackageRepository,
)
from src.provider.infrastructure.persistence.mysql_provider_repository import (
    MySQLProviderRepository,
)
from src.rates.application.use_cases.import_rates_from_excel import ImportRatesFromExcel
from src.rates.infrastructure.persistence.mysql_rates_repository import (
    MySQLRatesRepository,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.database.mysql_connection import get_connection
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.mega_dataframes import MegaDataFrames
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.mysql_special_repository import (
    MySQLSpecialRepository,
)


def import_rates(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)
    conn = get_connection()

    use_case = ImportRatesFromExcel(
        package_repo=MySQLPackageRepository(conn, logger),
        provider_repo=MySQLProviderRepository(conn, logger),
        special_repo=MySQLSpecialRepository(conn, logger),
        city_repo=MySQLCityRepository(conn, logger),
        activities_repo=MySQLActivityRepository(conn, logger),
        cup_repo=MySQLCupRepository(),
        fuzz=RapidFuzzBiller(conn, logger),
        progress=RichProgress(),
        loader=loader,
        mega=MegaDataFrames(conn),
        rates_repo=MySQLRatesRepository(conn, logger),
        logger=logger,
    )

    use_case.execute(excel)
