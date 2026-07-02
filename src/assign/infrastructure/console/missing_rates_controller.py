from src.assign.application.use_cases.missing_rates import MissingRates
from src.shared.console.file_input import ask_excel_path
from src.shared.console.file_output import ask_directory_path
from src.shared.console.progress import RichProgress
from src.shared.console.sheet_input import ask_sheet_name
from src.shared.excel.excel_loader import ExcelLoader


def generate_missing_rates(logger):
    loader = ExcelLoader()
    path = ask_excel_path()
    excel = loader.load(path)
    sheet = ask_sheet_name(excel.sheet_names)
    df = loader.load_sheet(excel, sheet)

    output_dir = ask_directory_path()
    output_path = output_dir / "faltantes.xlsx"

    use_case = MissingRates(progress=RichProgress(), logger=logger)
    use_case.execute(df, output_path)
