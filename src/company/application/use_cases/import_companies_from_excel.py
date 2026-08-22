import json
import os
from pathlib import Path

import polars as pl

from src.company.domain.entities.company import Company
from src.company.domain.entities.company_package import CompanyPackage
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.scrapping.domain.entities.nit_result import NitResult
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
        not_found_log_generator=None,
        logs_dir: Path = Path("logs"),
    ):
        self.company_repo = company_repo
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.fuzz = fuzz
        self.nit_service = nit_service
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)
        self.not_found_log_generator = not_found_log_generator
        self.logs_dir = logs_dir

    def execute(self, df: pl.DataFrame):
        self._progress_companies(df)
        self._progress_companies_to_packages(df)

    def _progress_companies(self, df: pl.DataFrame):
        file_path = os.path.join(os.getenv("DIRECTORY"), "data.json")
        df_nits = df.select(pl.col("NIT")).to_series().to_list()

        df_companies = pl.DataFrame(self.company_repo.all())
        pending_nits = df_nits
        if df_companies.height > 0:
            known = {str(n) for n in df_companies["nit"].to_list()}
            pending_nits = [n for n in df_nits if str(n) not in known]

        if not pending_nits:
            return

        cached: dict[str, NitResult] = {}
        if Path(file_path).exists():
            with self.progress("Cargando datos de empresas", total=1):
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                for d in data:
                    nit = str(d.get("nit"))
                    cached[nit] = NitResult(
                        nit=nit,
                        is_company=d.get("is_company", bool(d.get("name"))),
                        name=d.get("name"),
                        checked_bases=d.get("checked_bases", ""),
                    )
                self.progress.advance()

        still_pending = [n for n in pending_nits if str(n) not in cached]
        if still_pending:
            with self.progress("Validando NITs (Odoo/RUES)", total=len(still_pending)):
                new_results = self.nit_service.search(still_pending) or []
                self.progress.advance()
            for result in new_results:
                cached[str(result.nit)] = result
            self.nit_service.writer(list(cached.values()), file_path)

        result_scrapping = [
            cached[str(n)] for n in pending_nits if str(n) in cached
        ]

        razon_social_by_nit = {
            str(row["NIT"]).strip(): row["RAZON SOCIAL"]
            for row in df.iter_rows(named=True)
        }

        def _is_found(result) -> bool:
            return getattr(result, "is_company", bool(result.name)) and bool(result.name)

        not_found = [
            NitResult(
                nit=str(result.nit),
                is_company=False,
                name=result.name or razon_social_by_nit.get(str(result.nit)),
                checked_bases=getattr(result, "checked_bases", ""),
            )
            for result in result_scrapping
            if not _is_found(result)
        ]
        if not_found and self.not_found_log_generator:
            self.not_found_log_generator.generate(not_found, self.logs_dir)

        # Batch: collect unique companies by NIT (solo NITs nuevos y verificados), then insert
        companies_map = {}
        for result in result_scrapping:
            if _is_found(result):
                nit = str(result.nit).strip()[:9]
                companies_map[nit] = Company(nit, result.name.strip().upper())

        if companies_map:
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
