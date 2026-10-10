import json
import os
from pathlib import Path

import polars as pl

from src.billers.domain.entities.biller import Biller
from src.billers.domain.repositories.import_biller_from_excel_repository import (
    ImportBillerFromExcelRepository,
)
from src.company.domain.entities.company import Company
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    LOCAL_UPDATE_BOOK,
    LOCAL_UPDATE_COLUMNS,
)
from src.shared.config import get_paths_config
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.reporting.findings_writer import FindingsWriter, summarize_findings

BILLER_FINDING_COLUMNS = {
    "empresa_no_encontrada": ["NIT", "Facturador"],
    "facturador_no_encontrado": ["NIT", "Facturador"],
    "vinculacion_duplicada": ["NIT", "Empresa", "Facturador descartado", "Facturador vigente"],
    LOCAL_UPDATE_BOOK: LOCAL_UPDATE_COLUMNS[LOCAL_UPDATE_BOOK],
}


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
        file_path = os.path.join(get_paths_config()["directory"], "data.json")

        rows = df.select(["NIT", "GESTOR", "EMPRESA"]).drop_nulls()
        # Normalizar NIT: solo dígitos, max 9 chars
        rows = rows.with_columns(
            pl.col("NIT").str.replace_all(r"[^\d]", "").str.slice(0, 9).alias("NIT")
        ).filter(pl.col("NIT") != "")

        df_companies = pl.DataFrame(self.company_repo.all())
        new_nits = rows
        if df_companies.height > 0:
            new_nits = rows.filter(~pl.col("NIT").is_in(df_companies["nit"]))

        result_scrapping = []

        if len(new_nits) > 0:
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    result_scrapping = [
                        Company(d.get("nit"), d.get("name")) for d in data
                    ]
                # Buscar NITs que no estén en el archivo
                existing_nits = {str(r.nit) for r in result_scrapping}
                pending = [
                    n for n in new_nits["NIT"].to_list() if n not in existing_nits
                ]
                if pending:
                    new_results = self.nit_service.search(pending) or []
                    result_scrapping.extend(
                        Company(r.nit, r.name) for r in new_results if r.name
                    )
                    self.nit_service.writer(new_results, file_path)
            else:
                scraped = self.nit_service.search(new_nits["NIT"].to_list()) or []
                self.nit_service.writer(scraped, file_path)
                result_scrapping = [Company(r.nit, r.name) for r in scraped if r.name]
        elif Path(file_path).exists():
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
            nit = row["NIT"]
            gestor = row["GESTOR"].strip().upper()
            empresa = row["EMPRESA"].upper()
            companies_to_save[nit] = Company(nit, empresa)
            biller_name = self.fuzz.fuzz_property(gestor, biller_catalog) or gestor
            links.append((nit, biller_name))

        # Batch upsert companies
        with self.progress("Guardando compañías", total=1):
            self.company_repo.save_batch(list(companies_to_save.values()))
            self.progress.advance()

        # Build maps for linking (by NIT and by normalized name)
        all_companies_by_nit = {c["nit"]: c["id"] for c in self.company_repo.all()}
        all_companies_by_name = {
            c["name"].strip().upper(): c["id"] for c in self.company_repo.all()
        }
        all_billers = {b["name"]: b["id"] for b in self.biller_repo.all()}

        # Batch link
        link_pairs = []
        with self.progress("Vinculando compañías", total=len(links)):
            for nit, biller_name in links:
                company_id = all_companies_by_nit.get(nit)
                # Si no encuentra por NIT, buscar por nombre (caso duplicado)
                if not company_id:
                    empresa_name = companies_to_save.get(nit)
                    if empresa_name:
                        company_id = all_companies_by_name.get(
                            empresa_name.name.strip().upper()
                        )
                biller_id = all_billers.get(biller_name)
                if company_id and biller_id:
                    link_pairs.append((company_id, biller_id))
                elif not company_id:
                    self.logger.warning(
                        f"Company not found for NIT '{nit}' - cannot link to biller '{biller_name}'",
                        user_msg=f"Empresa NIT {nit} no encontrada para vincular con '{biller_name}'.",
                    )
                elif not biller_id:
                    self.logger.error(
                        f"Biller not found: '{biller_name}'",
                        user_msg=f"No se encontró el facturador '{biller_name}'.",
                    )
                self.progress.advance()

        if link_pairs:
            id_to_nit = {v: k for k, v in all_companies_by_nit.items()}
            id_to_biller_name = {v: k for k, v in all_billers.items()}
            unique_links = {}
            duplicados_log = []
            for company_id, biller_id in link_pairs:
                if company_id in unique_links:
                    nit = id_to_nit.get(company_id, "?")
                    empresa = next(
                        (
                            c.name
                            for c in companies_to_save.values()
                            if all_companies_by_nit.get(c.nit) == company_id
                        ),
                        "?",
                    )
                    biller = id_to_biller_name.get(biller_id, "?")
                    duplicados_log.append(
                        f"NIT {nit} - '{empresa}' → facturador '{biller}'"
                    )
                unique_links[company_id] = biller_id
            if duplicados_log:
                self.logger.error(
                    f"{len(duplicados_log)} vinculación(es) duplicada(s) omitida(s):",
                    user_msg=f"{len(duplicados_log)} vinculación(es) duplicada(s) omitida(s):",
                )

                for dup in duplicados_log:
                    self.logger.error(f"  {dup}", user_msg=f"  {dup}")
            self.biller_company_repo.link_or_update_batch(list(unique_links.items()))
