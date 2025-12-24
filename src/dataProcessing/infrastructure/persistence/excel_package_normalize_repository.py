import polars as pl

from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class NormalizePackage:
    def __init__(self, logger: LoggerAdapter = None, progress: RichProgress = None):
        self.logger = logger or LoggerAdapter(__name__)
        self.progress = progress

    def normalize(self, data) -> pl.DataFrame:
        try:
            total_steps = 6

            if self.progress:
                with self.progress("Normalizando paquetes", total=total_steps):
                    df_pkg = self._perform_normalization(data)
                    return df_pkg
            else:
                return self._perform_normalization(data)

        except Exception as identifier:
            self.logger.error(f"Error normalizing package: {identifier}", exc_info=True)

    def _perform_normalization(self, data):
        # Paso 1: Normalizar CONTRATO
        df_pkg = data.with_columns(
            pl.col("CONTRATO")
            .str.replace("[\\s]{2,}", " ")
            .str.strip_chars()
            .alias("CONTRATO")
        )
        if self.progress:
            self.progress.advance()

        # Paso 2: Normalizar CIUDAD
        df_pkg = df_pkg.with_columns(
            pl.col("CIUDAD")
            .str.replace("[\\s]{2,}", " ")
            .str.strip_chars()
            .alias("CIUDAD")
        )
        if self.progress:
            self.progress.advance()

        # Paso 3: Normalizar CUP
        df_pkg = df_pkg.with_columns(
            pl.col("CUP").str.replace("[\\s]{2,}", "").str.strip_chars().alias("CUP")
        )
        if self.progress:
            self.progress.advance()

        # Paso 4: Normalizar EXAMEN
        df_pkg = df_pkg.with_columns(
            pl.col("EXAMEN")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("EXAMEN")
        )
        if self.progress:
            self.progress.advance()

        # Paso 5: Normalizar INTRA O EXTRA
        df_pkg = df_pkg.with_columns(
            pl.col("INTRA O EXTRA")
            .str.replace("[\\s]{2,}", "")
            .str.strip_chars()
            .alias("INTRA O EXTRA")
        )
        if self.progress:
            self.progress.advance()

        # Paso 6: Implementación Columna Verified
        df_pkg = df_pkg.with_columns(
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

        return df_pkg
