import re

import polars as pl
from unidecode import unidecode

from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

NON_ALPHABETIC = re.compile(r"[^A-Za-z]")


class NormalizeSpecial:
    def __init__(self, logger: LoggerAdapter = None, progress: RichProgress = None):
        self.logger = logger or LoggerAdapter(__name__)
        self.progress = progress

    def normalize(self, data) -> pl.DataFrame:
        try:
            total_steps = 6
            if self.progress:
                with self.progress("Normalizando especiales", total=total_steps):
                    df_specials = self._perform_normalization(data)
                    return df_specials
            else:
                return self._perform_normalization(data)

        except Exception as identifier:
            self.logger.error(f"Error normalizing special: {identifier}", exc_info=True)

    def _perform_normalization(self, data):
        df_specials = data.sort("CONTRATO", descending=True)

        def _normalize_text(text: str) -> str:
            if text is None:
                return ""

            return NON_ALPHABETIC.sub("", unidecode(text).upper().strip())

        # Paso 1: Normalizar CONTRATO
        df_specials = df_specials.with_columns(
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
        df_specials = df_specials.with_columns(
            pl.col("CIUDAD")
            .str.replace("[\\s]{2,}", " ")
            .str.strip_chars()
            .alias("CIUDAD")
        )
        if self.progress:
            self.progress.advance()

        # Paso 3: Normalizar CUP
        df_specials = df_specials.with_columns(
            pl.col("CUP").str.replace("[\\s]{2,}", "").str.strip_chars().alias("CUP")
        )
        if self.progress:
            self.progress.advance()

        # Paso 4: Normalizar EXAMEN
        df_specials = df_specials.with_columns(
            pl.col("EXAMEN")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("EXAMEN")
        )
        if self.progress:
            self.progress.advance()

        # Paso 5: Normalizar INTRA O EXTRA
        df_specials = df_specials.with_columns(
            pl.col("INTRA O EXTRA")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("INTRA O EXTRA")
        )
        if self.progress:
            self.progress.advance()

        # Paso 6: Implementación Columna Verified
        df_specials = df_specials.with_columns(
            pl.when(pl.col("CUP").str.len_chars() < 6)
            .then(True)
            .when(
                pl.col("CUP").str.len_chars() > 6,
                ~pl.col("CUP").str.contains("-"),
            )
            .then(True)
            .otherwise(False)
            .alias("VERIFIED")
        )
        if self.progress:
            self.progress.advance()

        # Asignar el CONTRATO superior a cada grupo
        return df_specials.with_columns(
            pl.col("CONTRATO").first().over("slug").alias("CONTRATO")
        ).drop("slug")
