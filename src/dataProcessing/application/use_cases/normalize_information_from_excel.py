from pathlib import Path

from src.shared.excel.excel_loader import ExcelLoader


class NormalizeInformationFromExcel:
    def __init__(
        self,
        package,
        provider,
        special,
        export,
        novelties_log_generator=None,
        logs_dir: Path = Path("logs"),
    ):
        self.package = package
        self.provider = provider
        self.special = special
        self.export = export
        self.novelties_log_generator = novelties_log_generator
        self.logs_dir = logs_dir

    def execute(self, excel, loader, output):
        self._export_excel(excel, loader, output)

    def _export_excel(self, excel, loader: ExcelLoader = None, output: str = None):
        df_package = self.package.normalize(loader.load_sheet(excel, "Paquetes"))

        df_provider = self.provider.normalize(loader.load_sheet(excel, "Proveedores"))

        df_special = self.special.normalize(
            loader.load_sheets_by_prefix(excel, "TarifasEspeciales")
        )

        dataframes = {
            "Paquetes": df_package,
            "Proveedores": df_provider,
            "TarifasEspeciales": df_special,
        }

        self.export.export_dataframes(dataframes, output)

        if self.novelties_log_generator:
            novelties = (
                list(self.package.novelties)
                + list(self.provider.novelties)
                + list(self.special.novelties)
            )
            self.novelties_log_generator.generate(novelties, self.logs_dir)
