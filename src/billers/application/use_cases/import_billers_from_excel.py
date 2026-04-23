import json
import os
from pathlib import Path

import polars as pl

from src.billers.domain.entities.biller import Biller
from src.billers.domain.repositories.import_biller_from_excel_repository import (
    ImportBillerFromExcelRepository,
)
from src.company.domain.entities.company import Company
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class ImportBillersFromExcel(ImportBillerFromExcelRepository):
    def __init__(
        self,
        biller_repo,
        company_repo,
        biller_company_repo,
        nit_service,
        progress,
        fuzz,
        logger=None,
    ):
        self.biller_repo = biller_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.nit_service = nit_service
        self.progress = progress
        self.fuzz = fuzz
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, df):
        self._process_billers(df)
        self._process_companies(df)

    def _process_billers(self, df):
        gestores = df["GESTOR"].drop_nulls().unique()
        catalog = self.biller_repo.all()

        names_to_save = set()
        for gestor in gestores:
            name = gestor.strip().upper()
            if name in ("NAN", "NONE"):
                continue
            slug = self.fuzz.fuzz_property(name, catalog) if catalog else name
            if not slug:
                slug = name
            names_to_save.add(slug)

        with self.progress("Cargando facturadores", total=1):
            self.biller_repo.save_batch([Biller(n) for n in names_to_save])
            self.progress.advance()

    def _process_companies(self, df):
        file_path = os.path.join(os.getenv("DIRECTORY"), "data.json")

        rows = df.select(["NIT", "GESTOR", "EMPRESA"]).drop_nulls()

        df_companies = pl.DataFrame(self.company_repo.all())
        new_nits = rows
        if df_companies.height > 0:
            new_nits = rows.filter(~pl.col("NIT").is_in(df_companies["nit"]))

        result_scrapping = None

        if not Path(file_path).exists() and len(new_nits) > 0:
            result_scrapping = self.nit_service.search(new_nits["NIT"].to_list())
            self.nit_service.writer(result_scrapping, file_path)
        else:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                result_scrapping = [Company(d.get("nit"), d.get("name")) for d in data]

        nit_df = pl.DataFrame(
            {
                "NIT": [result.nit for result in result_scrapping if result.name],
                "EMPRESA_NUEVA": [
                    result.name for result in result_scrapping if result.name
                ],
            }
        )

        rows = rows.with_columns(pl.col("NIT").cast(pl.Utf8))
        nit_df = nit_df.with_columns(pl.col("NIT").cast(pl.Utf8))

        df_updated = (
            rows.join(nit_df, on="NIT", how="left")
            .with_columns(pl.coalesce(["EMPRESA_NUEVA", "EMPRESA"]).alias("EMPRESA"))
            .drop("EMPRESA_NUEVA")
        )

        biller_catalog = self.biller_repo.all()

        # Batch: collect companies and links, then upsert
        companies_to_save = {}  # nit -> Company
        links = []  # (nit, biller_name) to resolve after company save

        for row in df_updated.iter_rows(named=True):
            nit = row["NIT"][:9]
            gestor = row["GESTOR"].strip().upper()
            empresa = row["EMPRESA"].upper()
            companies_to_save[nit] = Company(nit, empresa)
            biller_name = self.fuzz.fuzz_property(gestor, biller_catalog) or gestor
            links.append((nit, biller_name))

        # Batch upsert companies
        with self.progress("Guardando compañías", total=1):
            self.company_repo.save_batch(list(companies_to_save.values()))
            self.progress.advance()

        # Build maps for linking
        all_companies = {c["nit"]: c["id"] for c in self.company_repo.all()}
        all_billers = {b["name"]: b["id"] for b in self.biller_repo.all()}

        # Batch link
        link_pairs = []
        with self.progress("Vinculando compañías", total=len(links)):
            for nit, biller_name in links:
                company_id = all_companies.get(nit)
                biller_id = all_billers.get(biller_name)
                if company_id and biller_id:
                    link_pairs.append((company_id, biller_id))
                elif not biller_id:
                    self.logger.error(
                        f"Biller not found: '{biller_name}'",
                        user_msg=f"No se encontró el facturador '{biller_name}'.",
                    )
                self.progress.advance()

        if link_pairs:
            self.biller_company_repo.link_or_update_batch(link_pairs)
