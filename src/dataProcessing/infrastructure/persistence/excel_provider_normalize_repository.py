import re

import polars as pl
from unidecode import unidecode

from src.cup.infrastructure.persistence.mysql_cup_repository import MySQLCupRepository
from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

NON_ALPHABETIC = re.compile(r"[^A-Za-z]")


class NormalizeProvider:
    def __init__(
        self,
        logger: LoggerAdapter = None,
        progress: RichProgress = None,
        cup_repository: MySQLCupRepository = None,
    ):
        self.logger = logger or LoggerAdapter(__name__)
        self.progress = progress
        self.cup_repository = cup_repository

    def normalize(self, data) -> pl.DataFrame:
        try:
            total_steps = 6
            if self.progress:
                with self.progress("Normalizando proveedores", total=total_steps):
                    df_providers = self._perform_normalization(data)
                    return df_providers
            else:
                return self._perform_normalization(data)

        except Exception as identifier:
            self.logger.error(
                f"Error normalizing provider: {identifier}", exc_info=True
            )

    def _perform_normalization(self, data):
        df_providers = data.sort("CONTRATO", descending=True)

        def _normalize_text(text: str) -> str:
            if text is None:
                return ""

            return NON_ALPHABETIC.sub("", unidecode(text).upper().strip())

        # Paso 1: Normalizar CONTRATO
        df_providers = df_providers.with_columns(
            pl.col("CONTRATO")
            .map_elements(_normalize_text, return_dtype=pl.Utf8)
            .alias("slug"),
            pl.col("CONTRATO")
            .str.replace("[\\s]{2,}", " ")
            .str.strip_chars()
            .alias("CONTRATO"),
        )

        if self.progress:
            self.progress.advance()

        # Paso 2: Normalizar CIUDAD
        df_providers = df_providers.with_columns(
            pl.col("CIUDAD")
            .str.replace("[\\s]{2,}", " ")
            .str.strip_chars()
            .alias("CIUDAD")
        )
        if self.progress:
            self.progress.advance()

        # Paso 3: Normalizar CUP
        df_providers = df_providers.with_columns(
            pl.col("CUP").str.replace("[\\s]{2,}", "").str.strip_chars().alias("CUP")
        )
        if self.progress:
            self.progress.advance()

        # Paso 4: Normalizar EXAMEN
        df_providers = df_providers.with_columns(
            pl.col("EXAMEN")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("EXAMEN")
        )
        if self.progress:
            self.progress.advance()

        # Paso 5: Normalizar INTRA O EXTRA
        df_providers = df_providers.with_columns(
            pl.col("INTRA O EXTRA")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("INTRA O EXTRA")
        )
        if self.progress:
            self.progress.advance()

        # Paso 6: Implementación Columna Verified
        df_providers = self._validate_cups_with_db(df_providers)
        if self.progress:
            self.progress.advance()

        # Asignar el CONTRATO superior a cada grupo
        return df_providers.with_columns(
            pl.col("CONTRATO").first().over("slug").alias("CONTRATO")
        ).drop("slug")

    def _validate_cups_with_db(self, df_providers):
        def _is_success(x: str) -> pl.Int64:
            if x is None:
                return None

            s = str(x)

            # Limpieza básica
            s = s.replace("\u00a0", "").replace(" ", "").replace("$", "")

            try:
                if len(s) >= 7:
                    price = int(s.split(".")[0])
                    return price
                else:
                    price = int(s.replace(".", ""))
            except ValueError:
                return None

            try:
                return int(float(s))
            except ValueError:
                return None

        if not self.cup_repository:
            return df_providers

        valid_cups = set(self.cup_repository.get_all_cups())

        # Crear columnas auxiliares para validación
        df_result = df_providers.with_columns(
            [
                pl.col("CUP").is_in(valid_cups).alias("cup_valid"),
                pl.col("VALOR").is_in(valid_cups).alias("valor_valid"),
            ]
        )

        # Identificar casos de intercambio
        swap_condition = ~pl.col("cup_valid") & pl.col("valor_valid")

        # Registrar errores en log
        swap_rows = df_result.filter(swap_condition)
        for row in swap_rows.select(["CUP", "VALOR", "CONTRATO"]).iter_rows():
            self.logger.error(
                f"CUP cruzado detectado. Intercambiando CUP: '{row[0]}' <-> VALOR: '{row[1]}' de contrato '{row[2]}'"
            )

        # Aplicar intercambios
        df_result = df_result.with_columns(
            [
                pl.when(swap_condition)
                .then(pl.col("VALOR"))
                .otherwise(pl.col("CUP"))
                .alias("CUP"),
                pl.when(swap_condition)
                .then(pl.col("CUP"))
                .otherwise(pl.col("VALOR"))
                .alias("VALOR"),
            ]
        )

        invalid_rows = df_result.filter(~pl.col("cup_valid") & ~pl.col("valor_valid"))
        for row in invalid_rows.select(["CUP"]).iter_rows():
            self.logger.error(f"CUP no existe en base de datos: '{row[0]}'")

        df_result = df_result.with_columns(
            pl.col("VALOR")
            .cast(pl.Utf8)
            .map_elements(_is_success, return_dtype=pl.Int64)
            .cast(pl.Int64)
            .alias("VALOR")
        )

        # Validacion Final
        return df_result.with_columns(
            pl.when(~pl.col("CUP").is_in(valid_cups))
            .then(True)
            .otherwise(False)
            .alias("VERIFIED")
        ).drop(["cup_valid", "valor_valid"])
