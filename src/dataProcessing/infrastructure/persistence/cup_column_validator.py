"""Valida y corrige la columna CUP de una hoja completa, vectorizado en Polars.

Único punto donde vive la lógica de validación de CUP (antes triplicada en
`_validate_cups_with_db` de los tres normalizadores). Aplica, en orden:
F0 intercambio CUP<->VALOR (comportamiento preexistente) y luego la cascada
F1-F4 de `CupResolver` sobre cada par distinto (CUP, EXAMEN) que sigue
inválido. Ver specs/005_correccion-cups-por-nombre/plan.md sección 3.4.
"""
import polars as pl

from src.dataProcessing.domain.entities.cup_novelty import (
    CupNovelty,
    ESTADO_CRUCE_CUP_VALOR,
    ESTADO_NO_CORREGIDO,
    FASE_SWAP,
)
from src.dataProcessing.domain.services.cup_resolver import CupResolver
from src.shared.utils.text_normalizer import normalize_text_key

_MAX_CONTRATOS_EJEMPLO = 5
_PAR_SEP = "\x00"


def _is_success(x: str):
    """Convierte VALOR a entero. Comportamiento preexistente (ver plan,
    no-objetivos: el bug de "5.000" -> 5 no se corrige en este feature)."""
    if x is None:
        return None

    s = str(x).replace(" ", "").replace(" ", "").replace("$", "")

    try:
        if len(s) >= 7:
            return int(s.split(".")[0])
        return int(s.replace(".", ""))
    except ValueError:
        pass

    try:
        return int(float(s))
    except ValueError:
        return None


class CupColumnValidator:
    def __init__(self, cup_repository, fuzz=None, threshold: int = 90):
        self._cup_repository = cup_repository
        self._fuzz = fuzz
        self._threshold = threshold

    def validate(self, df: pl.DataFrame, hoja: str) -> tuple[pl.DataFrame, list[CupNovelty]]:
        if not self._cup_repository:
            return df, []

        catalog = self._cup_repository.get_all()
        valid_codes = {c["code"].strip() for c in catalog}
        resolver = CupResolver(catalog, fuzz=self._fuzz, threshold=self._threshold)

        df = df.with_columns(pl.col("CUP").alias("CUP_ORIGINAL"))

        # --- F0: intercambio CUP <-> VALOR (comportamiento preexistente) ---
        df = df.with_columns(
            [
                pl.col("CUP").is_in(valid_codes).alias("_cup_valid"),
                pl.col("VALOR").is_in(valid_codes).alias("_valor_valid"),
                pl.col("VALOR").alias("_VALOR_ORIGINAL"),
            ]
        )
        swap_condition = (~pl.col("_cup_valid")) & pl.col("_valor_valid")
        df = df.with_columns(
            [
                pl.when(swap_condition).then(pl.col("VALOR")).otherwise(pl.col("CUP")).alias("CUP"),
                pl.when(swap_condition).then(pl.col("CUP")).otherwise(pl.col("VALOR")).alias("VALOR"),
            ]
        )
        df = df.with_columns(pl.col("CUP").is_in(valid_codes).alias("_cup_valid_now"))

        # --- clave normalizada de EXAMEN, solo sobre valores únicos ---
        unique_examenes = df["EXAMEN"].unique().to_list()
        key_map = {e: normalize_text_key(e) for e in unique_examenes if e is not None}
        df = df.with_columns(
            pl.col("EXAMEN").replace_strict(key_map, default=None).alias("_EXN")
        )

        # --- índice de co-ocurrencia: EXN -> códigos válidos distintos en la hoja ---
        coo_rows = (
            df.filter(pl.col("_cup_valid_now") & pl.col("_EXN").is_not_null())
            .group_by("_EXN")
            .agg(pl.col("CUP").unique().alias("cups"))
            .to_dicts()
        )
        coocurrence = {r["_EXN"]: r["cups"] for r in coo_rows}

        novelties: list[CupNovelty] = []
        correction_map: dict[str, str] = {}
        novedad_map: dict[str, str] = {}

        # --- novedades de F0, agrupadas por (CUP original, VALOR original) ---
        for row in (
            df.filter(swap_condition)
            .group_by(["CUP_ORIGINAL", "_VALOR_ORIGINAL"])
            .agg(pl.len().alias("filas"), pl.col("CONTRATO").unique().alias("contratos"))
            .to_dicts()
        ):
            orig_cup, orig_valor = row["CUP_ORIGINAL"], row["_VALOR_ORIGINAL"]
            novelties.append(
                CupNovelty(
                    hoja=hoja,
                    cup_original=orig_cup,
                    examen="",
                    cup_corregido=orig_valor,
                    detalle=f"'{orig_cup}' <-> '{orig_valor}'",
                    estado=ESTADO_CRUCE_CUP_VALOR,
                    fase=FASE_SWAP,
                    filas=row["filas"],
                    contratos=row["contratos"][:_MAX_CONTRATOS_EJEMPLO],
                )
            )

        # --- filas que siguen inválidas: se resuelven por PAR distinto (CUP, EXN) ---
        for row in (
            df.filter(~pl.col("_cup_valid_now"))
            .group_by(["CUP", "_EXN"])
            .agg(
                pl.len().alias("filas"),
                pl.col("EXAMEN").first().alias("examen_ejemplo"),
                pl.col("CONTRATO").unique().alias("contratos"),
            )
            .to_dicts()
        ):
            cup, exn, examen = row["CUP"], row["_EXN"], row["examen_ejemplo"]
            resolution = resolver.resolve(cup, examen, coocurrence)
            par = f"{cup}{_PAR_SEP}{exn or ''}"
            estado = resolution.estado or ESTADO_NO_CORREGIDO

            if resolution.corregido:
                correction_map[par] = resolution.cup
                novedad_map[par] = f"{estado} ('{cup}' -> '{resolution.cup}')"
                cup_corregido = resolution.cup
            else:
                novedad_map[par] = (
                    estado if not resolution.detalle else f"{estado}: {resolution.detalle}"
                )
                cup_corregido = None

            novelties.append(
                CupNovelty(
                    hoja=hoja,
                    cup_original=cup,
                    examen=examen or "",
                    cup_corregido=cup_corregido,
                    detalle=resolution.detalle,
                    estado=estado,
                    fase=resolution.fase or "",
                    filas=row["filas"],
                    contratos=row["contratos"][:_MAX_CONTRATOS_EJEMPLO],
                )
            )

        # --- aplicación vectorizada de las correcciones F1-F4 y del texto de NOVEDAD ---
        # La clave PAR se materializa ANTES de tocar CUP: si se calculara sobre
        # la columna CUP ya corregida, la búsqueda en correction_map/novedad_map
        # (construidos con el CUP original inválido) dejaría de coincidir.
        df = df.with_columns(
            (pl.col("CUP") + pl.lit(_PAR_SEP) + pl.col("_EXN").fill_null("")).alias("_PAR")
        )
        df = df.with_columns(
            pl.when(pl.col("_cup_valid_now"))
            .then(pl.col("CUP"))
            .otherwise(pl.col("_PAR").replace_strict(correction_map, default=None).fill_null(pl.col("CUP")))
            .alias("CUP")
        )
        cascade_novedad = pl.when(pl.col("_cup_valid_now")).then(pl.lit("")).otherwise(
            pl.col("_PAR").replace_strict(novedad_map, default="")
        )
        swap_novedad = (
            pl.lit(f"{ESTADO_CRUCE_CUP_VALOR} ('")
            + pl.col("CUP_ORIGINAL")
            + pl.lit("' -> '")
            + pl.col("_VALOR_ORIGINAL")
            + pl.lit("')")
        )
        df = df.with_columns(
            pl.when(swap_condition).then(swap_novedad).otherwise(cascade_novedad).alias("NOVEDAD")
        )

        # --- VALOR: cast final (comportamiento preexistente) ---
        df = df.with_columns(
            pl.col("VALOR")
            .cast(pl.Utf8)
            .map_elements(_is_success, return_dtype=pl.Int64)
            .cast(pl.Int64)
            .alias("VALOR")
        )

        # --- VERIFIED final: True = el CUP sigue sin existir tras la cascada ---
        df = df.with_columns((~pl.col("CUP").is_in(valid_codes)).alias("VERIFIED"))

        df = df.drop(
            ["_cup_valid", "_valor_valid", "_cup_valid_now", "_EXN", "_VALOR_ORIGINAL", "_PAR"]
        )

        return df, novelties
