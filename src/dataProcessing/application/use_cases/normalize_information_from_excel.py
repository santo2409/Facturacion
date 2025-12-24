from src.shared.excel.excel_loader import ExcelLoader


class NormalizeInformationFromExcel:
    def __init__(self, package, provider, special, export):
        self.package = package
        self.provider = provider
        self.special = special
        self.export = export

    def execute(self, excel, loader, output):
        self._export_excel(excel, loader, output)

    def _export_excel(self, excel, loader: ExcelLoader = None, output: str = None):
        df_package = self.package.normalize(loader.load_sheet(excel, "Paquetes"))

        df_provider = self.provider.normalize(loader.load_sheet(excel, "Proveedores"))

        df_special = self.special.normalize(
            loader.load_sheet(excel, "TarifasEspeciales")
        )

        dataframes = {
            "Paquetes": df_package,
            "Proveedores": df_provider,
            "TarifasEspeciales": df_special,
        }

        self.export.export_dataframes(dataframes, output)
