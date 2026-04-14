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

        with self.progress("Cargando facturadores", total=len(gestores)):
            for gestor in gestores:
                name = gestor.strip().upper()
                if name in ("NAN", "NONE"):
                    continue

                if catalog:
                    slug = self.fuzz.fuzz_property(name, catalog)
                else:
                    slug = name

                if not self.biller_repo.find_by_name(slug):
                    self.biller_repo.save(Biller(name))
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

        with self.progress("Vinculando compañías", total=len(df_updated)):
            for row in df_updated.iter_rows(named=True):
                nit = row["NIT"][:9]
                gestor = row["GESTOR"].strip().upper()
                empresa = row["EMPRESA"].upper()

                company = self.company_repo.find_by_nit(nit)
                if not company:
                    company = self.company_repo.save(Company(nit, empresa))

                biller_name = self.fuzz.fuzz_property(gestor, biller_catalog)
                if not biller_name:
                    biller_name = gestor

                biller = self.biller_repo.find_by_name(biller_name)
                if biller and company:
                    self.biller_company_repo.link_or_update(company[0], biller[0])
                elif not biller:
                    self.logger.error(
                        f"Biller not found: '{gestor}' -> '{biller_name}'", user_msg=f"No se encontró el facturador '{gestor}'. Verifique los datos del archivo."
                    )

                self.progress.advance()
