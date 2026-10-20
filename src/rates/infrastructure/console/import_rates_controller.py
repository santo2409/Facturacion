from pathlib import Path

from src.activity.infrastructure.sa_activity_type_repository import (
    SaActivityRepository,
)
from src.city.infrastructure.persistence.sa_city_repository import (
    SaCityRepository,
)
from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository
from src.package.infrastructure.persistence.sa_package_repository import (
    SaPackageRepository,
)
from src.provider.infrastructure.persistence.sa_provider_repository import (
    SaProviderRepository,
)
from src.rates.application.use_cases.import_rates_from_excel import ImportRatesFromExcel
from src.rates.infrastructure.persistence.sa_rates_repository import (
    SaRatesRepository,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.progress import RichProgress
from src.shared.database.database import get_session
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from src.shared.utils.mega_dataframes import MegaDataFrames
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.special.infrastructure.persistence.sa_special_repository import (
    SaSpecialRepository,
)
from src.shared.utils.deprecated import deprecated


def _build_use_case(session, logger, loader):
    return ImportRatesFromExcel(
        package_repo=SaPackageRepository(session, logger),
        provider_repo=SaProviderRepository(session, logger),
        special_repo=SaSpecialRepository(session, logger),
        city_repo=SaCityRepository(session, logger),
        activities_repo=SaActivityRepository(session, logger),
        cup_repo=SaCupRepository(session),
        fuzz=RapidFuzzBiller(logger),
        progress=RichProgress(),
        loader=loader,
        mega=MegaDataFrames(),
        rates_repo=SaRatesRepository(session, logger),
        logger=logger,
        findings_writer=XlsxFindingsWriter(Path("logs/cargar_tarifas")),
    )


@deprecated("Opción en desuso del menú")
def import_rates(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)
    session = get_session()

    use_case = _build_use_case(session, logger, loader)
    use_case.execute(excel)
