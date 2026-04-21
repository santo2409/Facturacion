from src.company.application.use_cases.import_companies_from_excel import (
    ImportCompaniesFromExcel,
)
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.package.infrastructure.persistence.sa_package_repository import (
    SaPackageRepository,
)
from src.provider.infrastructure.persistence.sa_provider_repository import (
    SaProviderRepository,
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


def import_companies(logger):
    path = ask_excel_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    session = get_session()

    use_case = ImportCompaniesFromExcel(
        company_repo=SaCompanyRepository(session, logger),
        package_repo=SaPackageRepository(session, logger),
        provider_repo=SaProviderRepository(session, logger),
        special_repo=SaSpecialRepository(session, logger),
        fuzz=RapidFuzzBiller(logger),
        nit_service=RUESNitService(logger),
        progress=RichProgress(),
        logger=logger,
    )

    use_case.execute(df)
