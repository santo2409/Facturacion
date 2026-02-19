import polars as pl
from rapidfuzz import process, utils


class CompanyNameNormalizer:
    def __init__(self, score_cutoff: int = 85, min_count: int = 1):
        self.score_cutoff = score_cutoff
        self.min_count = min_count

    def _clean_name(self, text: str) -> str:
        if text is None:
            return ""
        cleaned = utils.default_process(text)
        for suffix in [" sas", " sa", " bic", " ltda", " limitada", " esp", " eu"]:
            cleaned = cleaned.replace(suffix, "")
        return cleaned.strip().upper()

    def normalize_dataframe(self, df: pl.DataFrame, column: str, output_column: str = None) -> pl.DataFrame:
        if not output_column:
            output_column = f"{column}_Normalizada"
        
        df_temp = df.with_columns(
            pl.col(column).map_elements(self._clean_name, return_dtype=pl.String).alias("nombre_base")
        )
        
        referencias = (
            df_temp["nombre_base"]
            .value_counts()
            .filter(pl.col("count") > self.min_count)
            .sort("count", descending=True)["nombre_base"]
            .to_list()
        )
        
        def _normalize(name: str) -> str:
            if not name:
                return None
            match = process.extractOne(name, referencias, score_cutoff=self.score_cutoff)
            return match[0] if match else name
        
        unicos = df_temp.select("nombre_base").unique()
        mapeo = unicos.with_columns(
            pl.col("nombre_base").map_elements(_normalize, return_dtype=pl.String).alias(output_column)
        )
        
        return df_temp.join(mapeo, on="nombre_base", how="left").drop("nombre_base")
