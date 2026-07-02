import re
from pathlib import Path

import polars as pl

from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class MissingRates:
    def __init__(self, progress: RichProgress, logger: LoggerAdapter):
        self.progress = progress
        self.logger = logger

    def execute(self, df: pl.DataFrame, output_path: Path):
        cup_cols = [c for c in df.columns if re.match(r"^\d", c)]
        df = df.cast({c: pl.Utf8 for c in cup_cols})

        result = pl.DataFrame()

        with self.progress("Procesando faltantes", total=len(cup_cols)):
            for col in cup_cols:
                filtered = df.filter(pl.col(col) == "1").select(
                    "NIT", "Empresa", "PAQUETE", "Ciudad", "TIPO DE ACTIVIDAD", "Base"
                )
                if filtered.height == 0:
                    self.progress.advance()
                    continue

                enriched = filtered.with_columns(
                    Examen=pl.lit(col),
                    ToDo=pl.concat_str(
                        [
                            pl.col("NIT"),
                            pl.col("PAQUETE"),
                            pl.col("Ciudad"),
                            pl.col("TIPO DE ACTIVIDAD"),
                            pl.lit(col),
                            pl.col("Base"),
                        ],
                        separator="",
                    ),
                )
                result = pl.concat([result, enriched])
                self.progress.advance()

        if result.height > 0:
            result = result.unique(subset=["ToDo"]).drop("ToDo")

        result.write_excel(
            str(output_path),
            worksheet="Faltantes",
            table_style="Table Style Medium 2",
        )

        self.logger.info(
            f"Faltantes generados: {result.height} registros en {output_path}",
            user_msg=f"{result.height} registros faltantes exportados.",
        )
