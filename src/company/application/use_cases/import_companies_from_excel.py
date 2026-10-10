import json
import os
from pathlib import Path

import polars as pl

from src.company.domain.entities.company import Company
from src.company.domain.entities.company_package import CompanyPackage
from src.company.domain.entities.unlinked_row import UnlinkedRow
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.config import get_paths_config
from src.shared.console.progress import RichProgress
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    LOCAL_UPDATE_BOOK,
    LOCAL_UPDATE_COLUMNS,
)
from src.shared.reporting.findings_writer import FindingsWriter, summarize_findings
from src.shared.utils.document_normalizer import normalize_document

COMPANY_FINDING_COLUMNS = {
    "documento_acotado": ["Documento original", "Documento acotado"],
    "paquetes_en_conflicto": ["Documento", "Paquete descartado", "Paquete vigente"],
    "paquete_no_encontrado": ["Documento", "Razón social", "Paquete"],
    LOCAL_UPDATE_BOOK: LOCAL_UPDATE_COLUMNS[LOCAL_UPDATE_BOOK],
}
from src.special.domain.entities.special import Special


class ImportCompaniesFromExcel:
    _CATALOG_SCHEMA = {"id": pl.Int64, "name": pl.Utf8, "model": pl.Utf8}

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
        not_linked_log_generator=None,
        findings_writer: FindingsWriter | None = None,
        rues_cache_loader=None,
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
        self.not_linked_log_generator = not_linked_log_generator
        self._dv_warning_count = 0
        self._companies_created = 0
        self._links_persisted = 0
        self._unlinked_count = 0
        self._empty_catalogs: list[str] = []
        self.findings_writer = findings_writer
        self.rues_cache_loader = rues_cache_loader
        self._reset_findings()

    def _reset_findings(self):
        self._findings: dict[str, list[dict]] = {key: [] for key in COMPANY_FINDING_COLUMNS}

    def execute(self, df: pl.DataFrame):
        self._reset_findings()
        self._progress_companies(df)
        self._progress_companies_to_packages(df)
        self._emit_summary()

    def _emit_summary(self):
        folder = self.findings_writer.write(self._findings, COMPANY_FINDING_COLUMNS) if self.findings_writer else None
        findings_summary = summarize_findings(self._findings, folder)
        self.logger.info(
            (
                f"Resumen importación empresas: {self._companies_created} creada(s), "
                f"{self._links_persisted} vinculación(es) persistida(s), "
                f"{self._unlinked_count} fila(s) sin vincular, "
                f"{self._dv_warning_count} documento(s) acotado(s) con DV inválido."
            ),
            user_msg=(
                f"Empresas creadas: {self._companies_created}. "
                f"Vinculaciones persistidas: {self._links_persisted}. "
                f"Filas sin vincular: {self._unlinked_count}. "
                f"{findings_summary}"
            ),
        )

    def _progress_companies(self, df: pl.DataFrame):
        self._dv_warning_count = 0
        self._companies_created = 0

        file_path = os.path.join(get_paths_config()["directory"], "data.json")
        raw_nits = df.select(pl.col("NIT")).to_series().to_list()
        normalized_by_raw = {raw: normalize_document(raw) for raw in raw_nits}

        for raw, doc in normalized_by_raw.items():
            if doc.truncated and doc.dv_valid is False:
                self._dv_warning_count += 1
                self.logger.warning(
                    f"Posible error de digitación: '{raw}' se acotó a '{doc.value}' (DV no coincide)",
                )
                self._findings["documento_acotado"].append(
                    {"Documento original": raw, "Documento acotado": doc.value}
                )

        doc_values = [doc.value for doc in normalized_by_raw.values()]

        df_companies = pl.DataFrame(self.company_repo.all())
        known: set[str] = set()
        if df_companies.height > 0:
            known = {normalize_document(n).value for n in df_companies["nit"].to_list()}

        if not doc_values:
            return

        # Odoo es la fuente de verdad: todos los documentos del Excel se validan contra
        # Odoo, también los que ya están en la BD local. `data.json` solo aporta
        # resultados de RUES, que evitan volver a consultar RUES (spec 016).
        rues_cache = self.rues_cache_loader(file_path) if self.rues_cache_loader else {}
        with self.progress("Validando NITs (Odoo/RUES)", total=1):
            results = self.nit_service.search(
                list(dict.fromkeys(doc_values)), rues_cache=rues_cache
            ) or []
            self.progress.advance()
        self.nit_service.writer(results, file_path)
        self._findings[LOCAL_UPDATE_BOOK] = list(getattr(self.nit_service, "local_updates", []))

        cached = {normalize_document(r.nit).value: r for r in results}
        result_scrapping = [cached[d] for d in doc_values if d in cached]

        razon_social_by_nit = {
            normalize_document(row["NIT"]).value: row["RAZON SOCIAL"]
            for row in df.iter_rows(named=True)
        }

        def _is_found(result) -> bool:
            return getattr(result, "is_company", bool(result.name)) and bool(result.name)

        not_found = [
            NitResult(
                nit=str(result.nit),
                is_company=False,
                name=result.name or razon_social_by_nit.get(normalize_document(result.nit).value),
                checked_bases=getattr(result, "checked_bases", ""),
            )
            for result in result_scrapping
            if not _is_found(result)
        ]
        if not_found and self.not_found_log_generator:
            self.not_found_log_generator.generate(not_found, self.logs_dir)

        # Batch: collect unique companies by documento normalizado (solo nuevos y verificados)
        companies_map = {}
        for result in result_scrapping:
            if _is_found(result):
                doc = normalize_document(result.nit)
                companies_map[doc.value] = Company(doc.value, result.name.strip().upper())

        if companies_map:
            with self.progress("Importando empresas", total=1):
                self.company_repo.save_batch(list(companies_map.values()))
                self._companies_created = len(companies_map)
                self.progress.advance()

    def _catalog_frame(self, rows, model_name: str, label: str) -> pl.DataFrame:
        """Construye el frame de un origen del catálogo (packages/providers/
        specials) con esquema explícito. Un origen vacío o en error (`all()`
        devuelve `None`) no aporta ninguna fila y se advierte, señalando el
        paso previo del flujo que pudo no ejecutarse (RF-01, RF-03)."""
        if not rows:
            self._empty_catalogs.append(label)
            self.logger.warning(
                (
                    f"Catálogo de {label} vacío al vincular empresas a paquetes: "
                    "verifica que se hayan ejecutado la opción 3 (Tratamiento "
                    "Información) y la opción 4 (Cargar Tarifas)."
                ),
                user_msg=(
                    f"El catálogo de {label} está vacío; verifica que se hayan "
                    "ejecutado la opción 3 (Tratamiento Información) y la "
                    "opción 4 (Cargar Tarifas) antes de continuar."
                ),
            )
            return pl.DataFrame(schema=self._CATALOG_SCHEMA)
        return (
            pl.DataFrame(rows)
            .with_columns(pl.lit(model_name).alias("model"))
            .select(["id", "name", "model"])
        )

    def _build_package_catalog(self) -> pl.DataFrame:
        """Catálogo unificado paquetes+proveedores+especiales, robusto ante
        orígenes vacíos (RF-01). Cada llamada reinicia el registro de
        orígenes vacíos de la corrida."""
        self._empty_catalogs = []
        pkg = self._catalog_frame(self.package_repo.all(), Package.__name__, "paquetes")
        prov = self._catalog_frame(self.provider_repo.all(), Provider.__name__, "proveedores")
        spec = self._catalog_frame(self.special_repo.all(), Special.__name__, "tarifas especiales")
        return pl.concat([pkg, prov, spec], how="vertical")

    def _report_no_catalog(self, df: pl.DataFrame):
        """RF-04: los tres orígenes están vacíos. No se vincula nada; se
        informa al usuario, se reportan todas las filas y no se propaga
        ninguna excepción."""
        reason = "No hay catálogo de paquetes cargado"
        unlinked_rows = [
            UnlinkedRow(
                document=row["NIT"],
                company_name=row["RAZON SOCIAL"],
                package=row["PAQUETE"],
                reason=reason,
            )
            for row in df.iter_rows(named=True)
        ]
        self._unlinked_count = len(unlinked_rows)
        self.logger.warning(
            "No hay catálogo de paquetes cargado (packages/providers/specials "
            "vacíos); no se ejecuta la vinculación.",
            user_msg=(
                "No hay catálogo de paquetes cargado. Ejecuta la opción 3 "
                "(Tratamiento Información) y la opción 4 (Cargar Tarifas) "
                "antes de registrar empresas."
            ),
        )
        if unlinked_rows and self.not_linked_log_generator:
            self.not_linked_log_generator.generate(unlinked_rows, self.logs_dir)

    def _progress_companies_to_packages(self, df: pl.DataFrame):
        self._links_persisted = 0
        self._unlinked_count = 0

        df = df.with_columns(
            pl.col("NIT")
            .map_elements(lambda x: normalize_document(x).value)
            .alias("NIT")
        )

        todo = self._build_package_catalog()

        if todo.height == 0:
            self._report_no_catalog(df)
            return

        catalog = [{"name": n} for n in todo["name"].to_list()]
        catalog_local = catalog

        df = df.with_columns(
            pl.col("PAQUETE")
            .map_elements(
                lambda x, c=catalog_local: self.fuzz.fuzz_property(x, c, 95) or x
            )
            .alias("PAQUETE")
        )

        # Build lookup maps (claves normalizadas en ambos lados, RF-05)
        all_companies = {
            normalize_document(c["nit"]).value: (c["id"], c["nit"], c["name"])
            for c in self.company_repo.all()
        }
        pkg_name_map = {row["name"]: (row["id"], row["model"]) for row in todo.to_dicts()}

        # Deduplicar por company_id: última fila gana (RF-08)
        batch_by_company: dict[int, CompanyPackage] = {}
        conflict_info: dict[int, tuple[str, str]] = {}
        unlinked_rows: list[UnlinkedRow] = []

        with self.progress("Vinculando empresas a paquetes", total=df.height):
            for row in df.iter_rows(named=True):
                nit = row["NIT"]
                found = all_companies.get(nit)
                if not found:
                    self.logger.warning(
                        f"Empresa no encontrada para documento '{nit}'",
                        user_msg=f"No se encontró la empresa con documento '{nit}'.",
                    )
                    unlinked_rows.append(
                        UnlinkedRow(
                            document=nit,
                            company_name=row["RAZON SOCIAL"],
                            package=row["PAQUETE"],
                            reason="Empresa no encontrada en la base de datos",
                        )
                    )
                    self.progress.advance()
                    continue

                company_id, _, _ = found
                pkg_info = pkg_name_map.get(row["PAQUETE"])
                if pkg_info:
                    package_id, model = pkg_info
                    existing = batch_by_company.get(company_id)
                    if existing is not None:
                        previous_pkg_name, _ = conflict_info.get(
                            company_id, (None, None)
                        )
                        self.logger.warning(
                            f"Vinculación duplicada para documento '{nit}': "
                            f"se descarta '{previous_pkg_name}' y prevalece '{row['PAQUETE']}'",
                            user_msg=(
                                f"El documento '{nit}' tiene paquetes en conflicto: "
                                f"se descartó '{previous_pkg_name}' y quedó '{row['PAQUETE']}'."
                            ),
                        )
                    batch_by_company[company_id] = CompanyPackage(company_id, package_id, model)
                    conflict_info[company_id] = (row["PAQUETE"], model)
                else:
                    self.logger.warning(
                        f"Package not found: {row['PAQUETE']}",
                        user_msg=f"No se encontró el paquete '{row['PAQUETE']}'.",
                    )
                self.progress.advance()

        batch = list(batch_by_company.values())
        if batch:
            self.company_repo.companies_packages_batch(batch)
            self._links_persisted = len(batch)

        self._unlinked_count = len(unlinked_rows)
        if unlinked_rows and self.not_linked_log_generator:
            self.not_linked_log_generator.generate(unlinked_rows, self.logs_dir)
