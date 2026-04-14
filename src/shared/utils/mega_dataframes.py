import polars as pl

from src.shared.excel.excel_loader import ExcelLoader


class MegaDataFrames:
    def __init__(self, conn):
        self.conn = conn

    def total_dataframe(
        self, loader: ExcelLoader, excel, callback: str
    ) -> pl.DataFrame:
        sheets = excel.sheet_names

        df_packages = loader.load_sheet(excel, "Paquetes") if "Paquetes" in sheets else pl.DataFrame()
        df_providers = loader.load_sheet(excel, "Proveedores") if "Proveedores" in sheets else pl.DataFrame()
        df_specials = loader.load_sheet(excel, "TarifasEspeciales") if "TarifasEspeciales" in sheets else pl.DataFrame()

        if callback == "Paquetes":
            frames_to_concat = []

            if not df_packages.is_empty():
                df_packages = df_packages.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                )
                frames_to_concat.append(df_packages)

            if not df_providers.is_empty():
                df_providers = df_providers.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                ).filter(
                    pl.col("CONTRATO").str.starts_with("TARIFA")
                    | pl.col("CONTRATO").str.starts_with("PAQUETE")
                )
                frames_to_concat.append(df_providers)

            if not df_specials.is_empty():
                df_specials = df_specials.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                ).filter(
                    pl.col("CONTRATO").str.starts_with("TARIFA")
                    | pl.col("CONTRATO").str.starts_with("PAQUETE")
                )
                frames_to_concat.append(df_specials)

            return pl.concat(frames_to_concat) if frames_to_concat else pl.DataFrame()

        elif callback == "Proveedores":
            frames_to_concat = []

            df_packages = df_packages.filter(
                pl.col("CONTRATO").str.contains("PROVEEDOR")
            )

            df_specials = df_specials.filter(
                pl.col("CONTRATO").str.contains("PROVEEDOR")
            )

            df_providers = pl.concat([df_providers, df_packages, df_specials])

            return df_providers

        elif callback == "TarifasEspeciales":
            df_specials = df_specials.with_columns(
                pl.col("CONTRATO")
                .str.replace_all("TARIFAS", "TARIFA")
                .str.replace_all("PAQUETES", "PAQUETE")
                .str.strip_chars()
                .str.to_uppercase()
            )

            df_specials = df_specials.filter(
                ~pl.col("CONTRATO").str.contains("PROVEEDOR")
                & ~pl.col("CONTRATO").str.contains("PAQUETE")
                & ~pl.col("CONTRATO").str.contains("TARIFA")
            )

            return df_specials

        else:
            df_cities = pl.concat([df_specials, df_providers, df_packages])
            return df_cities
