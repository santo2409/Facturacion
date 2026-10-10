import polars as pl

from src.city.domain.entities.city import City
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.rates.domain.entities.rate import Rate
from src.shared.console.progress import RichProgress
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.mega_dataframes import MegaDataFrames
from src.shared.reporting.findings_writer import FindingsWriter, summarize_findings
from src.special.domain.entities.special import Special

_ORIGIN_COLUMNS = ["Hoja", "Fila", "CONTRATO", "CIUDAD", "CUP", "INTRA O EXTRA", "VALOR"]
RATE_FINDING_COLUMNS = {
    key: _ORIGIN_COLUMNS
    for key in (
        "contrato_no_existe",
        "ciudad_no_existe",
        "cup_no_existe",
        "actividad_invalida",
        "tarifa_vacia",
    )
}


class ImportRatesFromExcel:
    def __init__(
        self,
        package_repo,
        provider_repo,
        special_repo,
        city_repo,
        activities_repo,
        cup_repo,
        fuzz,
        progress: RichProgress = None,
        loader: ExcelLoader = None,
        mega: MegaDataFrames = None,
        rates_repo=None,
        logger=None,
        findings_writer: FindingsWriter | None = None,
    ):
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.city_repo = city_repo
        self.activities_repo = activities_repo
        self.cup_repo = cup_repo
        self.progress = progress
        self.loader = loader
        self.fuzz = fuzz
        self.mega = mega
        self.rates_repo = rates_repo
        self.logger = logger
        self.findings_writer = findings_writer
        self._reset_findings()

    def _reset_findings(self):
        self._findings: dict[str, list[dict]] = {key: [] for key in RATE_FINDING_COLUMNS}
        self._seen_findings: set[tuple] = set()

    def _add_finding(self, key: str, row: dict):
        hoja, fila = row.get("_HOJA"), row.get("_FILA")
        # Una misma fila puede pasar por más de un callback (paquetes, proveedores,
        # especiales): con origen conocido se reporta una sola vez por tipo.
        if fila is not None:
            marker = (key, hoja, fila)
            if marker in self._seen_findings:
                return
            self._seen_findings.add(marker)
        self._findings[key].append({
            "Hoja": hoja,
            "Fila": fila,
            "CONTRATO": row["CONTRATO"],
            "CIUDAD": row["CIUDAD"],
            "CUP": row["CUP"],
            "INTRA O EXTRA": row["INTRA O EXTRA"],
            "VALOR": row.get("_VALOR_ORIG", row["VALOR"]),
        })

    def _publish_findings(self):
        folder = self.findings_writer.write(self._findings, RATE_FINDING_COLUMNS) if self.findings_writer else None
        summary = summarize_findings(self._findings, folder)
        self.logger.info(f"Resumen de hallazgos de tarifas: {summary}", user_msg=summary)

    def execute(self, excel):
        self._reset_findings()
        self._progress_city(excel)
        self._progress_packages(excel)
        self._progress_providers(excel)
        self._progress_specials(excel)
        self._publish_findings()

    def _resolve_names(self, raw_names, catalog):
        """Apply fuzzy matching and return deduplicated resolved names."""
        resolved = set()
        for name in raw_names:
            upper = name.upper()
            if catalog and upper not in [c["name"] for c in catalog]:
                slug = self.fuzz.fuzz_property(upper, catalog, threshold=95)
                resolved.add(slug if slug else upper)
            else:
                resolved.add(upper)
        return list(resolved)

    def _resolve_names_with_renames(self, raw_names, catalog):
        """Like _resolve_names but also returns {old_name: new_name} for fuzzy matches that differ."""
        resolved = set()
        renames = {}
        for name in raw_names:
            upper = name.upper()
            if catalog and upper not in [c["name"] for c in catalog]:
                slug = self.fuzz.fuzz_property(upper, catalog, threshold=95)
                if slug and slug != upper:
                    # Fuzzy matched to an existing name that differs → rename
                    renames[slug] = upper
                    resolved.add(upper)
                else:
                    resolved.add(slug if slug else upper)
            else:
                resolved.add(upper)
        return list(resolved), renames

    def _progress_city(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Ciudades")
        cities = df["CIUDAD"].unique().to_list()
        city_all = self.city_repo.all()

        resolved = self._resolve_names(cities, city_all)
        city_entities = [City(name) for name in resolved]

        with self.progress("Importando ciudades", total=1):
            self.city_repo.save_batch(city_entities)
            self.progress.advance()

    def _progress_packages(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Paquetes")
        packages = df["CONTRATO"].unique().to_list()
        package_all = self.package_repo.all()

        resolved = self._resolve_names(packages, package_all)
        pkg_entities = [Package(name) for name in resolved]

        with self.progress("Importando paquetes", total=1):
            self.package_repo.save_batch(pkg_entities)
            self.progress.advance()

        self.__relationships_rates(df, self.package_repo.all(), Package.__name__)

    def _progress_providers(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Proveedores")
        providers = df["CONTRATO"].unique().to_list()
        provider_all = self.provider_repo.all()

        resolved = self._resolve_names(providers, provider_all)
        prov_entities = [Provider(name) for name in resolved]

        with self.progress("Importando proveedores", total=1):
            self.provider_repo.save_batch(prov_entities)
            self.progress.advance()

        self.__relationships_rates(df, self.provider_repo.all(), Provider.__name__)

    def _progress_specials(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "TarifasEspeciales")
        specials = df["CONTRATO"].unique().to_list()
        special_all = self.special_repo.all()

        resolved, renames = self._resolve_names_with_renames(specials, special_all)
        new_names = [name for name in resolved if name not in renames.values()]
        spec_entities = [Special(name) for name in new_names]

        with self.progress("Importando tarifas especiales", total=1):
            if spec_entities:
                self.special_repo.save_batch(spec_entities)
            for old_name, new_name in renames.items():
                spec_id = next((s["id"] for s in special_all if s["name"] == old_name), None)
                if spec_id:
                    self.special_repo.update(Special(new_name, id=spec_id))
            self.progress.advance()

        self.__relationships_rates(df, self.special_repo.all(), Special.__name__)

    def __relationships_rates(self, df: pl.DataFrame, contract_all, model):
        city_all = self.city_repo.all()
        activities_all = self.activities_repo.all()
        cups_all = self.cup_repo.get_all()

        contract_map = {c["name"]: c["id"] for c in contract_all}
        city_map = {c["name"]: c["id"] for c in city_all}
        cup_map = {c["code"]: c["id"] for c in cups_all}
        activity_map = {c["name"]: c["id"] for c in activities_all}

        # Build fuzzy city alias map for names not in catalog
        city_alias = {}
        for city_name in df["CIUDAD"].unique().to_list():
            upper = city_name.upper()
            if upper not in city_map:
                slug = self.fuzz.fuzz_property(upper, city_all, threshold=90)
                if slug:
                    city_alias[upper] = city_map[slug]

        df = df.with_columns(pl.col("VALOR").cast(pl.Utf8).alias("_VALOR_ORIG"))
        df = df.with_columns(
            pl.col("VALOR").cast(pl.Utf8).str.replace_all(r"\D", "").alias("VALOR")
        )
        df = df.with_columns(
            pl.col("INTRA O EXTRA").fill_null("INTRA").alias("INTRA O EXTRA")
        )

        batch_size = 1000
        rates_batch = []

        try:
            with self.progress("Importando tarifas", total=len(df)):
                for row in df.iter_rows(named=True):
                    contract_id = contract_map.get(row["CONTRATO"].upper())
                    city_id = city_map.get(row["CIUDAD"].upper()) or city_alias.get(row["CIUDAD"].upper())
                    cup_id = cup_map.get(row["CUP"].upper())
                    activity_id = activity_map.get(row["INTRA O EXTRA"].upper())
                    rate_value = row["VALOR"]

                    if not contract_id:
                        self.logger.error(
                            f"Contrato no encontrado: '{row['CONTRATO']}'",
                        )
                        self._add_finding("contrato_no_existe", row)
                        self.progress.advance()
                        continue

                    if not city_id:
                        self.logger.error(
                            f"Ciudad no encontrada: '{row['CIUDAD']}' en contrato '{row['CONTRATO']}'",
                        )
                        self._add_finding("ciudad_no_existe", row)
                        self.progress.advance()
                        continue

                    if not cup_id:
                        self.logger.error(
                            f"CUP no encontrado: '{row['CUP']}' en contrato '{row['CONTRATO']}'",
                        )
                        self._add_finding("cup_no_existe", row)
                        self.progress.advance()
                        continue

                    if not activity_id:
                        self.logger.error(
                            f"Actividad no encontrada: '{row['INTRA O EXTRA']}' en contrato '{row['CONTRATO']}'",
                        )
                        self._add_finding("actividad_invalida", row)
                        self.progress.advance()
                        continue

                    if not rate_value:
                        self.logger.error(
                            f"Valor vacío para CUP '{row['CUP']}' en contrato '{row['CONTRATO']}'",
                        )
                        self._add_finding("tarifa_vacia", row)
                        self.progress.advance()
                        continue

                    rates_batch.append(
                        Rate(
                            rateable_id=contract_id,
                            city_id=city_id,
                            cup_id=cup_id,
                            rate=int(rate_value),
                            activity_id=activity_id,
                            rateable_type=model,
                        )
                    )

                    if len(rates_batch) >= batch_size:
                        self._save_deduped(rates_batch)
                        rates_batch = []

                    self.progress.advance()

                if rates_batch:
                    self._save_deduped(rates_batch)

        except Exception as error:
            self.logger.error(
                f"Error saving rates: {error}",
                exc_info=True,
                user_msg="No se pudieron guardar las tarifas.",
            )

    def _save_deduped(self, rates_batch: list[Rate]):
        """Deduplicate by conflict key before inserting."""
        unique = {}
        for r in rates_batch:
            key = (r.rateable_id, r.city_id, r.cup_id, r.activity_id, r.rateable_type)
            unique[key] = r
        self.rates_repo.save_batch(list(unique.values()))
