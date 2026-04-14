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

    def _progress_city(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Ciudades")
        cities = df["CIUDAD"].unique()
        city_all = self.city_repo.all()

        with self.progress("Importando ciudades", total=len(cities)):
            for city in cities:
                city_upper = city.upper()
                if city_upper not in city_all and len(city_all) > 0:
                    slug = self.fuzz.fuzz_property(city_upper, city_all)
                    if not slug:
                        slug = city_upper
                else:
                    slug = city_upper

                if not self.city_repo.find_by_name(slug):
                    self.city_repo.save(City(slug))
                self.progress.advance()

    def _progress_packages(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Paquetes")

        packages = df["CONTRATO"].unique()
        package_all = self.package_repo.all()

        with self.progress("Importando paquetes", total=len(packages)):
            for package in packages:
                package_upper = package.upper()
                if package_upper not in package_all and len(package_all) > 0:
                    slug = self.fuzz.fuzz_property(package_upper, package_all)
                    if not slug:
                        slug = package_upper
                else:
                    slug = package_upper

                if not self.package_repo.find_by_name(slug):
                    self.package_repo.save(Package(slug))
                self.progress.advance()

        self.__relationships_rates(df, package_all, Package.__name__)

    def _progress_providers(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Proveedores")
        providers = df["CONTRATO"].unique()
        provider_all = self.provider_repo.all()

        with self.progress("Importando proveedores", total=len(providers)):
            for provider in providers:
                provider_upper = provider.upper()
                existing = self.provider_repo.find_by_name(provider_upper)

                if not existing and len(provider_all) > 0:
                    fuzzy_match = self.fuzz.fuzz_property(provider_upper, provider_all)
                    if fuzzy_match:
                        existing_record = self.provider_repo.find_by_name(fuzzy_match)
                        if existing_record:
                            provider_entity = Provider(
                                name=provider_upper, id=existing_record[0]
                            )
                            self.provider_repo.update(provider_entity)
                    else:
                        self.provider_repo.save(Provider(provider_upper))
                elif not existing:
                    self.provider_repo.save(Provider(provider_upper))

                self.progress.advance()

        self.__relationships_rates(df, self.provider_repo.all(), Provider.__name__)

    def _progress_specials(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "TarifasEspeciales")
        specials = df["CONTRATO"].unique()
        special_all = self.special_repo.all()

        with self.progress("Importando tarifas especiales", total=len(specials)):
            for special in specials:
                special_upper = special.upper()
                existing = self.special_repo.find_by_name(special_upper)

                if not existing and len(special_all) > 0:
                    fuzzy_match = self.fuzz.fuzz_property(special_upper, special_all)
                    if fuzzy_match:
                        existing_record = self.special_repo.find_by_name(fuzzy_match)
                        if existing_record:
                            special_entity = Special(
                                name=special_upper, id=existing_record[0]
                            )
                            self.special_repo.update(special_entity)
                    else:
                        self.special_repo.save(Special(special_upper))
                elif not existing:
                    self.special_repo.save(Special(special_upper))

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
