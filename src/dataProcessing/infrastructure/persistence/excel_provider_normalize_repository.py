import re

import polars as pl
from unidecode import unidecode

from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository
from src.dataProcessing.domain.entities.cup_novelty import CupNovelty
from src.dataProcessing.infrastructure.persistence.cup_column_validator import (
    CupColumnValidator,
)
from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter

NON_ALPHABETIC = re.compile(r"[^A-Za-z]")


class NormalizeProvider:
    SHEET_LABEL = "Proveedores"

    def __init__(
        self,
        logger: LoggerAdapter = None,
        progress: RichProgress = None,
        cup_repository: SaCupRepository = None,
        fuzz=None,
    ):
        self.logger = logger or LoggerAdapter(__name__)
        self.progress = progress
        self.cup_repository = cup_repository
        self.novelties: list[CupNovelty] = []
        self._validator = (
            CupColumnValidator(cup_repository, fuzz) if cup_repository else None
        )

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
                f"Error normalizing provider: {identifier}",
                exc_info=True,
                user_msg="Error al procesar el proveedor. Verifique el formato del archivo.",
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

        # Paso 6: Validar/corregir CUP contra la BD (columnas CUP_ORIGINAL,
        # NOVEDAD, VERIFIED). Ver CupColumnValidator para la cascada F0-F4.
        df_providers = self._validate_cups_with_db(df_providers)
        if self.progress:
            self.progress.advance()

        # Asignar el CONTRATO superior a cada grupo
        return df_providers.with_columns(
            pl.col("CONTRATO").first().over("slug").alias("CONTRATO")
        ).drop("slug")

    def _validate_cups_with_db(self, df_providers):
        if not self._validator:
            return df_providers
        df_providers, self.novelties = self._validator.validate(
            df_providers, self.SHEET_LABEL
        )
        return df_providers
