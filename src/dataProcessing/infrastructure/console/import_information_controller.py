from src.dataProcessing.application.use_cases.normalize_information_from_excel import (
    NormalizeInformationFromExcel,
)
from src.dataProcessing.infrastructure.persistence.excel_package_normalize_repository import (
    NormalizePackage,
)
from src.dataProcessing.infrastructure.persistence.excel_provider_normalize_repository import (
    NormalizeProvider,
)
from src.dataProcessing.infrastructure.persistence.excel_special_normalize_repository import (
    NormalizeSpecial,
)
from src.shared.console.file_input import ask_excel_path
from src.shared.console.file_output import ask_directory_path
from src.shared.console.progress import RichProgress
from src.shared.excel.excel_exporter import ExcelExporter
from src.shared.excel.excel_loader import ExcelLoader


def import_information(logger):
    path = ask_excel_path()
    output = ask_directory_path()
    loader = ExcelLoader()
    excel = loader.load(path)

    use_case = NormalizeInformationFromExcel(
        package=NormalizePackage(logger, RichProgress()),
        provider=NormalizeProvider(logger, RichProgress()),
        special=NormalizeSpecial(logger, RichProgress()),
        export=ExcelExporter(RichProgress()),
    )

    use_case.execute(excel, loader, output)
