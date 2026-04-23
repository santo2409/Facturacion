import polars as pl

from src.city.domain.entities.city import City
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.rates.domain.entities.rate import Rate
from src.shared.console.progress import RichProgress
from src.shared.excel.excel_loader import ExcelLoader
from src.shared.utils.mega_dataframes import MegaDataFrames
from src.special.domain.entities.special import Special


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

    def execute(self, excel):
        self._progress_city(excel)
        self._progress_packages(excel)
        self._progress_providers(excel)
        self._progress_specials(excel)

    def _resolve_names(self, raw_names, catalog):
        """Apply fuzzy matching and return deduplicated resolved names."""
        resolved = set()
        for name in raw_names:
            upper = name.upper()
            if catalog and upper not in [c["name"] for c in catalog]:
                slug = self.fuzz.fuzz_property(upper, catalog)
                resolved.add(slug if slug else upper)
            else:
                resolved.add(upper)
        return list(resolved)

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

        self.__relationships_rates(df, package_all, Package.__name__)

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

        resolved = self._resolve_names(specials, special_all)
        spec_entities = [Special(name) for name in resolved]

        with self.progress("Importando tarifas especiales", total=1):
            self.special_repo.save_batch(spec_entities)
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
                    city_id = city_map.get(row["CIUDAD"].upper())
                    cup_id = cup_map.get(row["CUP"].upper())
                    activity_id = activity_map.get(row["INTRA O EXTRA"].upper())
                    rate_value = row["VALOR"]

                    if all(
                        [
                            contract_id,
                            city_id,
                            cup_id,
                            activity_id,
                            rate_value is not None,
                        ]
                    ):
                        rates_batch.append(
                            Rate(
                                rateable_id=contract_id,
                                city_id=city_id,
                                cup_id=cup_id,
                                rate=rate_value,
                                activity_id=activity_id,
                                rateable_type=model,
                            )
                        )

                    if len(rates_batch) >= batch_size:
                        self.rates_repo.save_batch(rates_batch)
                        rates_batch = []

                    self.progress.advance()

                if rates_batch:
                    self.rates_repo.save_batch(rates_batch)

        except Exception as error:
            self.logger.error(
                f"Error saving rates: {error}",
                exc_info=True,
                user_msg="No se pudieron guardar las tarifas.",
            )
