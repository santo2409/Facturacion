import json
import os
from pathlib import Path

import polars as pl

from src.company.domain.entities.company import Company
from src.company.domain.entities.company_package import CompanyPackage
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.special.domain.entities.special import Special


class ImportCompaniesFromExcel:
    def __init__(
        self,
        company_repo,
        package_repo,
        provider_repo,
        special_repo,
        fuzz,
        nit_service,
        progress: RichProgress,
        logger: LoggerAdapter,
    ):
        self.company_repo = company_repo
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.fuzz = fuzz
        self.nit_service = nit_service
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, df: pl.DataFrame):
        self._progress_companies(df)
        self._progress_companies_to_packages(df)

    def _progress_companies(self, df: pl.DataFrame):
        file_path = os.path.join(os.getenv("DIRECTORY"), "data.json")
        df_nits = df.select(pl.col("NIT")).to_series().to_list()
        result_scrapping = None

        if not Path(file_path).exists():
            with self.progress("Validando NITs (RUES)", total=len(df_nits)):
                result_scrapping = self.nit_service.search(df_nits)
                self.progress.advance()
            self.nit_service.writer(result_scrapping, file_path)
        else:
            with self.progress("Cargando datos de empresas", total=1):
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    result_scrapping = [
                        Company(d.get("nit"), d.get("company")) for d in data
                    ]
                self.progress.advance()

        nit_df = pl.DataFrame(
            {
                "NIT": [result.nit for result in result_scrapping if result.name],
                "EMPRESA_NUEVA": [
                    result.name for result in result_scrapping if result.name
                ],
            }
        )

        df = df.with_columns(pl.col("NIT").cast(pl.Utf8))
        nit_df = nit_df.with_columns(pl.col("NIT").cast(pl.Utf8))

        df_updated = (
            df.join(nit_df, on="NIT", how="left")
            .with_columns(
                pl.coalesce(["EMPRESA_NUEVA", "RAZON SOCIAL"]).alias("RAZON SOCIAL")
            )
            .drop("EMPRESA_NUEVA")
        )

        # Batch: collect unique companies by NIT, then upsert
        companies_map = {}
        for row in df_updated.iter_rows(named=True):
            nit = str(row["NIT"]).strip()[:9]
            empresa = row["RAZON SOCIAL"].strip().upper()
            companies_map[nit] = Company(nit, empresa)

        with self.progress("Importando empresas", total=1):
            self.company_repo.save_batch(list(companies_map.values()))
            self.progress.advance()

    def _progress_companies_to_packages(self, df: pl.DataFrame):
        pkg = pl.DataFrame(self.package_repo.all())
        pkg = pkg.with_columns(pl.lit(Package.__name__).alias("model"))
        prov = pl.DataFrame(self.provider_repo.all())
        prov = prov.with_columns(pl.lit(Provider.__name__).alias("model"))
        spec = pl.DataFrame(self.special_repo.all())
        spec = spec.with_columns(pl.lit(Special.__name__).alias("model"))

        todo = pl.concat([pkg, prov, spec], how="vertical")

        df = df.with_columns(
            pl.col("NIT")
            .cast(pl.Utf8)
            .str.replace_all(r"\D", "")
            .str.slice(0, 9)
            .alias("NIT")
        )

        catalog = [{"name": n} for n in todo["name"].to_list()]
        catalog_local = catalog

        df = df.with_columns(
            pl.col("PAQUETE")
            .map_elements(
                lambda x, c=catalog_local: self.fuzz.fuzz_property(x, c, 95) or x
            )
            .alias("PAQUETE")
        )

        # Build lookup maps
        all_companies = {c["nit"]: c["id"] for c in self.company_repo.all()}
        pkg_name_map = {row["name"]: (row["id"], row["model"]) for row in todo.to_dicts()}

        # Collect batch
        batch = []
        with self.progress("Vinculando empresas a paquetes", total=df.height):
            for row in df.iter_rows(named=True):
                nit = row["NIT"][:9].strip()
                company_id = all_companies.get(nit)
                if not company_id:
                    self.progress.advance()
                    continue

                pkg_info = pkg_name_map.get(row["PAQUETE"])
                if pkg_info:
                    package_id, model = pkg_info
                    batch.append(CompanyPackage(company_id, package_id, model))
                else:
                    self.logger.warning(
                        f"Package not found: {row['PAQUETE']}",
                        user_msg=f"No se encontró el paquete '{row['PAQUETE']}'.",
                    )
                self.progress.advance()

        if batch:
            self.company_repo.companies_packages_batch(batch)
