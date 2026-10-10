import openpyxl
import polars as pl

from src.shared.excel.excel_loader import ExcelLoader


class MegaDataFrames:
    def __init__(self):
        self._rows_cache: dict[tuple[str, str], list[int] | None] = {}

    def _excel_rows(self, excel, sheet: str) -> list[int] | None:
        """Número de fila en Excel de cada fila de datos de la hoja.

        El lector (polars + calamine) descarta las filas totalmente vacías y no
        informa dónde empieza la hoja, así que numerar en secuencia desfasa el
        reporte. Se leen las posiciones reales una sola vez por hoja. Devuelve None
        si openpyxl no puede leer el archivo (p. ej. .xls): se numera en secuencia."""
        key = (str(excel.path), sheet)
        if key not in self._rows_cache:
            try:
                wb = openpyxl.load_workbook(excel.path, read_only=True, data_only=True)
                try:
                    filled = [
                        n for n, values in enumerate(wb[sheet].iter_rows(values_only=True), start=1)
                        if any(v is not None for v in values)
                    ]
                finally:
                    wb.close()
                self._rows_cache[key] = filled[1:]  # la primera fila con datos es el encabezado
            except Exception:
                self._rows_cache[key] = None
        return self._rows_cache[key]

    def _load_tagged(self, loader: ExcelLoader, excel, sheet: str) -> pl.DataFrame:
        """Carga la hoja y etiqueta cada fila con su hoja y su número de fila en
        Excel, para poder reportar hallazgos con origen. Las columnas internas
        `_HOJA` y `_FILA` quedan al final y no se persisten."""
        df = loader.load_sheet(excel, sheet)
        rows = self._excel_rows(excel, sheet)
        if rows is None or len(rows) != df.height:  # ilegible o inconsistente: en secuencia
            rows = list(range(2, df.height + 2))
        return df.with_columns(
            pl.lit(sheet).alias("_HOJA"),
            pl.Series("_FILA", rows, dtype=pl.Int64),
        )

    def _load_specials(self, loader: ExcelLoader, excel) -> pl.DataFrame:
        sheets = [s for s in excel.sheet_names if s.startswith("TarifasEspeciales")]
        if not sheets:
            return pl.DataFrame()
        return pl.concat(
            [self._load_tagged(loader, excel, s) for s in sheets], how="vertical_relaxed"
        )

    def total_dataframe(
        self, loader: ExcelLoader, excel, callback: str
    ) -> pl.DataFrame:
        sheets = excel.sheet_names

        df_packages = self._load_tagged(loader, excel, "Paquetes") if "Paquetes" in sheets else pl.DataFrame()
        df_providers = self._load_tagged(loader, excel, "Proveedores") if "Proveedores" in sheets else pl.DataFrame()
        df_specials = self._load_specials(loader, excel)

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

            if not df_providers.is_empty():
                df_providers = df_providers.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                )
                frames_to_concat.append(df_providers)

            if not df_packages.is_empty():
                df_packages = df_packages.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                ).filter(
                    pl.col("CONTRATO").str.contains("PROVEEDOR")
                )
                frames_to_concat.append(df_packages)

            if not df_specials.is_empty():
                df_specials = df_specials.with_columns(
                    pl.col("CONTRATO")
                    .str.replace_all("TARIFAS", "TARIFA")
                    .str.replace_all("PAQUETES", "PAQUETE")
                    .str.strip_chars()
                    .str.to_uppercase()
                ).filter(
                    pl.col("CONTRATO").str.contains("PROVEEDOR")
                )
                frames_to_concat.append(df_specials)

            return pl.concat(frames_to_concat) if frames_to_concat else pl.DataFrame()

        elif callback == "TarifasEspeciales":
            if df_specials.is_empty():
                return pl.DataFrame()

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
            frames_to_concat = []
            if not df_specials.is_empty():
                frames_to_concat.append(df_specials)
            if not df_providers.is_empty():
                frames_to_concat.append(df_providers)
            if not df_packages.is_empty():
                frames_to_concat.append(df_packages)
            return pl.concat(frames_to_concat) if frames_to_concat else pl.DataFrame()
