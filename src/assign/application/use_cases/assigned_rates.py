import json
import os
import re

import polars as pl

from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.text_normalizer import (
    normalize_name,
    pl_normalize_name,
    pl_normalize_upper,
)
from src.special.domain.entities.special import Special


def _enrich_with_invoices(df: pl.DataFrame, df_facture: pl.DataFrame, logger) -> pl.DataFrame:
    """Añade columna FACTURAS a df cruzando por N° Identificación."""
    id_col = "N° Identificación"
    fac_col = "# FACTURA"

    df = df.with_columns(
        pl.col(id_col).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias(id_col)
    )

    df_facture = (
        df_facture
        .with_columns(
            pl.col(id_col).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias(id_col)
        )
        .unique(subset=[id_col, fac_col])
    )

    duplicados = df_facture.group_by(id_col).len().filter(pl.col("len") > 1).height
    if duplicados:
        logger.warning(f"{duplicados} identificaciones con más de una factura. Se concatenarán.")

    df_grp = df_facture.group_by(id_col).agg(
        pl.col(fac_col).str.join(", ").alias("FACTURAS")
    )

    df = df.join(df_grp, on=id_col, how="left").with_columns(
        pl.col("FACTURAS").fill_null("")
    )

    sin_factura = df.filter(pl.col("FACTURAS") == "").height
    logger.info(
        f"Enriquecimiento facturas: {df.height - sin_factura} con match, {sin_factura} sin factura.",
        user_msg=f"{df.height - sin_factura} registros con factura asignada.",
    )
    return df


class AssignRatesFromExcel:
    def __init__(
        self,
        biller_repo,
        company_repo,
        biller_company_repo,
        package_repo,
        provider_repo,
        special_repo,
        city_repo,
        activities_repo,
        rates_repo,
        cup_repo,
        nit_service,
        fuzz,
        progress,
        logger,
    ):
        self.biller_repo = biller_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.city_repo = city_repo
        self.activities_repo = activities_repo
        self.rates_repo = rates_repo
        self.cup_repo = cup_repo
        self.nit_service = nit_service
        self.fuzz = fuzz
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, excel: pl.DataFrame, df_facture: pl.DataFrame):
        lookups = self._build_lookups()
        df = self._normalize_nit(excel)
        df = self._match_companies(df, lookups)
        df = self._normalize_columns(df)
        df = self._normalize_city(df, lookups)
        df = self._assign_facturador(df, lookups)
        df = self._assign_paquete(df, lookups)
        df = self._assign_rates(df, lookups)
        df = self._validate_empresa(df, lookups)
        df = _enrich_with_invoices(df, df_facture, self.logger)
        df = self._order_columns(df)

        with self.progress("Exportando consolidado", total=1):
            df.write_excel(
                "CONSOLIDADO.xlsx",
                worksheet="Consolidado",
                table_style="Table Style Medium 2",
            )
            self.progress.advance()

    # ── Column ordering ───────────────────────────────────────────────────

    _FIXED_COLUMNS_ORDER = [
        "Base",
        "Ingreso N°",
        "Sede",
        "Ciudad",
        "NIT",
        "FACTURADOR",
        "Especial / General",
        "PAQUETE",
        "Empresa",
        "Empresa Misión",
        "Medio de Pago",
        "Fecha Ingreso",
        "Tipo Examen",
        "Cargo",
        "Paciente",
        "N° Identificación",
        "Número de Póliza",
        "ORDEN, CENTRO DE COSTO, CECO, PET",
        "ORDEN, CENTRO DE COSTO, CECO, PET_1",
        "FACTURAS",
        "TIPO DE ACTIVIDAD",
        "Observaciones Ingreso",
        "Total",
    ]

    def _order_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        fixed = [c for c in self._FIXED_COLUMNS_ORDER if c in df.columns]
        others = sorted(
            [c for c in df.columns if c not in set(self._FIXED_COLUMNS_ORDER)],
            key=lambda x: (int(x.split("-")[0]) if x.replace("-", "").isdigit() else float("inf"), x),
        )
        return df.select(fixed + others)

    # ── Build lookup dictionaries O(1) ────────────────────────────────────

    def _build_lookups(self) -> dict:
        companies_all = self.company_repo.all()
        biller_companies_all = self.biller_company_repo.all()
        billers_all = self.biller_repo.all()
        companies_rates_all = self.company_repo.companies_packages_all()
        packages_all = self.package_repo.all()
        providers_all = self.provider_repo.all()
        special_all = self.special_repo.all()
        cities_all = self.city_repo.all()
        activity_all = self.activities_repo.all()
        cup_all = self.cup_repo.get_all()

        # NIT → company dict
        nit_to_company = {c["nit"]: c for c in companies_all}
        # company_id → (package_id, model)
        company_to_package = {c["company"]: (c["package"], c["model"]) for c in companies_rates_all}
        # company_id → biller_id
        company_to_biller = {bc["company"]: bc["biller"] for bc in biller_companies_all}
        # biller_id → name
        biller_id_to_name = {b["id"]: b["name"] for b in billers_all}
        # city name → id
        city_name_to_id = {c["name"]: c["id"] for c in cities_all}
        # cup code → id
        cup_code_to_id = {c["code"].strip(): c["id"] for c in cup_all}
        # activity name → id
        activity_name_to_id = {c["name"]: c["id"] for c in activity_all}
        # package name → (id, model)
        package_name_to_id = {c["name"]: (c["id"], Package.__name__) for c in packages_all}

        # Scraped NITs from JSON
        scraped_nits = {}
        json_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                for item in json.load(f):
                    nit = str(item.get("nit", ""))
                    if nit:
                        scraped_nits[nit] = item.get("name", "")

        return {
            "nit_to_company": nit_to_company,
            "company_to_package": company_to_package,
            "company_to_biller": company_to_biller,
            "biller_id_to_name": biller_id_to_name,
            "city_name_to_id": city_name_to_id,
            "cup_code_to_id": cup_code_to_id,
            "activity_name_to_id": activity_name_to_id,
            "package_name_to_id": package_name_to_id,
            "scraped_nits": scraped_nits,
            "cities_all": cities_all,
            "packages_all": packages_all,
        }

    # ── NIT normalization ─────────────────────────────────────────────────

    def _normalize_nit(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(
            pl.col("NIT")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.extract_all(r"\d+")
            .list.first()
            .str.slice(0, 9)
            .alias("NIT")
        )

    # ── Match companies by NIT ────────────────────────────────────────────

    def _match_companies(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        scraped_nits = lookups["scraped_nits"]

        matched_nits = []
        matched_empresas = []
        for row in df.iter_rows(named=True):
            nit = row["NIT"]
            empresa = row["Empresa"]
            base = row["Base"]

            if nit and nit in nit_to_company:
                matched_nits.append(nit)
                matched_empresas.append(nit_to_company[nit]["name"])
            elif nit and nit in scraped_nits and scraped_nits[nit]:
                matched_nits.append(nit)
                matched_empresas.append(scraped_nits[nit])
            else:
                if nit:
                    self.logger.warning(
                        f"NIT {nit} - {empresa} no encontrado, registrado por {base}",
                        user_msg=f"El NIT {nit} no fue encontrado en el sistema.",
                    )
                matched_nits.append(nit)
                matched_empresas.append(empresa)

        return df.with_columns([
            pl.Series("NIT", matched_nits),
            pl.Series("Empresa", matched_empresas),
        ])

    # ── Column normalization ──────────────────────────────────────────────

    def _normalize_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns([
            pl_normalize_name("Empresa").alias("Empresa"),
            pl_normalize_name("Empresa Misión").alias("Empresa Misión"),
            pl_normalize_name("Sede").alias("Sede"),
            pl_normalize_upper("Medio de Pago").cast(pl.Utf8).alias("Medio de Pago"),
            pl_normalize_upper("Tipo Examen").cast(pl.Utf8).alias("Tipo Examen"),
            (
                pl.col("Cargo")
                .str.strip_chars()
                .str.to_uppercase()
                .str.replace_all(r"[^A-Z&Ñ#0-9\s]", "")
                .str.replace_all(r"\s+", " ")
                .cast(pl.Utf8)
                .alias("Cargo")
            ),
            pl_normalize_name("Paciente").cast(pl.Utf8).alias("Paciente"),
            (
                pl.col("TIPO DE ACTIVIDAD")
                .fill_null("INTRA")
                .str.strip_chars()
                .str.to_uppercase()
                .str.replace_all("INTRAMURAL", "INTRA")
                .str.replace_all("EXTRAMURAL", "EXTRA")
                .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                .cast(pl.Utf8)
                .alias("TIPO DE ACTIVIDAD")
            ),
        ])

    # ── City normalization with pre-computed fuzzy ─────────────────────────

    def _normalize_city(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        cities_all = lookups["cities_all"]
        unique_cities = df["Ciudad"].unique().to_list()

        # Fuzzy match only unique values
        city_map = {}
        for city in unique_cities:
            if city is None:
                city_map[city] = city
                continue
            upper = str(city).upper()
            result = self.fuzz.fuzz_property(upper, cities_all)
            city_map[city] = result if result else upper

        return df.with_columns(
            pl.col("Ciudad").replace(city_map).alias("Ciudad")
        )

    # ── Assign FACTURADOR via join ────────────────────────────────────────

    def _assign_facturador(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_biller = lookups["company_to_biller"]
        biller_id_to_name = lookups["biller_id_to_name"]

        # Build NIT → facturador_name mapping
        nit_to_facturador = {}
        for nit, comp in nit_to_company.items():
            biller_id = company_to_biller.get(comp["id"])
            if biller_id:
                name = biller_id_to_name.get(biller_id, "GENERAL")
                nit_to_facturador[nit] = name
            else:
                nit_to_facturador[nit] = "GENERAL"

        # Build lookup DataFrame and join
        if nit_to_facturador:
            df_fact = pl.DataFrame({
                "NIT": list(nit_to_facturador.keys()),
                "FACTURADOR": list(nit_to_facturador.values()),
            })
            df = df.join(df_fact, on="NIT", how="left").with_columns(
                pl.col("FACTURADOR").fill_null("GENERAL")
            )
        else:
            df = df.with_columns(pl.lit("GENERAL").alias("FACTURADOR"))

        df = df.with_columns(
            pl.when(pl.col("FACTURADOR") == "GENERAL")
            .then(pl.lit("GENERAL"))
            .otherwise(pl.lit("ESPECIAL"))
            .alias("Especial / General")
        )
        return df

    # ── Assign PAQUETE via join ───────────────────────────────────────────

    def _assign_paquete(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_package = lookups["company_to_package"]
        packages_all = lookups["packages_all"]

        # Build NIT → package_name mapping
        nit_to_pkg = {}
        for nit, comp in nit_to_company.items():
            pkg_tuple = company_to_package.get(comp["id"])
            if pkg_tuple:
                pkg_id, model = pkg_tuple
                # Find name by id and model
                if model == Package.__name__:
                    name = next((p["name"] for p in packages_all if p["id"] == pkg_id), None)
                elif model == Provider.__name__:
                    name = next((p["name"] for p in self.provider_repo.all() if p["id"] == pkg_id), None)
                elif model == Special.__name__:
                    name = next((p["name"] for p in self.special_repo.all() if p["id"] == pkg_id), None)
                else:
                    name = next((p["name"] for p in packages_all if p["id"] == 30), None)
                nit_to_pkg[nit] = name
            else:
                nit_to_pkg[nit] = next((p["name"] for p in packages_all if p["id"] == 30), None)

        if nit_to_pkg:
            df_pkg = pl.DataFrame({
                "NIT": list(nit_to_pkg.keys()),
                "PAQUETE": list(nit_to_pkg.values()),
            })
            df = df.join(df_pkg, on="NIT", how="left")
        else:
            df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias("PAQUETE"))

        return df

    # ── Assign rates with batch query ─────────────────────────────────────

    def _assign_rates(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_package = lookups["company_to_package"]
        city_name_to_id = lookups["city_name_to_id"]
        cup_code_to_id = lookups["cup_code_to_id"]
        activity_name_to_id = lookups["activity_name_to_id"]
        package_name_to_id = lookups["package_name_to_id"]

        headers = [h for h in df.columns if str(h).replace("-", "").isdigit()]

        # Cast CUP columns to Int64
        for h in headers:
            df = df.with_columns(pl.col(str(h)).cast(pl.Int64))

        # Phase 1: Collect all unique rate keys needed
        rate_keys_set = set()
        rows_data = df.select(["NIT", "Ciudad", "TIPO DE ACTIVIDAD", "PAQUETE"] + [str(h) for h in headers]).to_dicts()

        with self.progress("Calculando tarifas", total=len(rows_data)):
            for row in rows_data:
                nit = row["NIT"]
                city = row["Ciudad"]
                activity = row["TIPO DE ACTIVIDAD"]
                pkg_name = row["PAQUETE"]

                # Resolve package_id and model
                comp = nit_to_company.get(nit)
                if comp:
                    pkg_tuple = company_to_package.get(comp["id"])
                else:
                    pkg_tuple = None

                if pkg_tuple:
                    package_id, model = pkg_tuple
                elif pkg_name and pkg_name in package_name_to_id:
                    package_id, model = package_name_to_id[pkg_name]
                else:
                    self.progress.advance()
                    continue

                city_id = city_name_to_id.get(city)
                activity_id = activity_name_to_id.get(activity)

                if not all([package_id, city_id, activity_id]):
                    self.progress.advance()
                    continue

                for h in headers:
                    if row.get(str(h)) == 1:
                        cup_id = cup_code_to_id.get(str(h).strip())
                        if cup_id:
                            rate_keys_set.add((package_id, city_id, cup_id, activity_id, model))

                self.progress.advance()

        # Phase 2: Batch query all needed rates
        self.logger.info(
            f"Consultando {len(rate_keys_set)} combinaciones únicas de tarifas",
            user_msg=f"Consultando {len(rate_keys_set)} tarifas en lote...",
        )
        rates_cache = self.rates_repo.find_batch(list(rate_keys_set))
        self.logger.info(
            f"Encontradas {len(rates_cache)} tarifas de {len(rate_keys_set)} consultadas",
            user_msg=f"{len(rates_cache)} tarifas encontradas.",
        )

        # Phase 3: Build result columns
        result_cols = {str(h): df[str(h)].to_list() for h in headers}

        for idx, row in enumerate(rows_data):
            nit = row["NIT"]
            city = row["Ciudad"]
            activity = row["TIPO DE ACTIVIDAD"]
            pkg_name = row["PAQUETE"]

            comp = nit_to_company.get(nit)
            if comp:
                pkg_tuple = company_to_package.get(comp["id"])
            else:
                pkg_tuple = None

            if pkg_tuple:
                package_id, model = pkg_tuple
            elif pkg_name and pkg_name in package_name_to_id:
                package_id, model = package_name_to_id[pkg_name]
            else:
                continue

            city_id = city_name_to_id.get(city)
            activity_id = activity_name_to_id.get(activity)

            if not all([package_id, city_id, activity_id]):
                continue

            for h in headers:
                if row.get(str(h)) == 1:
                    cup_id = cup_code_to_id.get(str(h).strip())
                    if cup_id:
                        key = (package_id, city_id, cup_id, activity_id, model)
                        price = rates_cache.get(key, 1)
                        result_cols[str(h)][idx] = int(price)

        # Replace columns with computed values
        for h in headers:
            df = df.with_columns(pl.Series(str(h), result_cols[str(h)]).cast(pl.Int64))

        # Total column
        if headers:
            df = df.with_columns(
                pl.sum_horizontal([pl.col(str(h)) for h in headers]).alias("Total")
            )
        else:
            df = df.with_columns(pl.lit(0).alias("Total"))

        self.logger.info(
            f"Columna Total generada: {len(headers)} columnas CUP, {df.height} filas",
            user_msg=f"Columna Total calculada para {df.height} registros.",
        )
        return df

    # ── Validate Empresa matches DB ───────────────────────────────────────

    def _validate_empresa(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]

        db_nit_to_name = {
            nit: normalize_name(c["name"])
            for nit, c in nit_to_company.items()
        }

        # Check mismatches
        mismatches = 0
        for row in df.iter_rows(named=True):
            nit = row["NIT"]
            if nit and nit in db_nit_to_name and row["Empresa"] != db_nit_to_name[nit]:
                mismatches += 1

        if mismatches:
            self.logger.warning(
                f"{mismatches} empresas no coinciden con BD. Corrigiendo.",
                user_msg=f"{mismatches} nombres de empresa corregidos según la base de datos.",
            )
            df = df.with_columns(
                pl.struct(["NIT", "Empresa"])
                .map_elements(
                    lambda s: db_nit_to_name.get(s["NIT"], s["Empresa"]),
                    return_dtype=pl.Utf8,
                )
                .alias("Empresa")
            )

        return df
