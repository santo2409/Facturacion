import polars as pl

from src.city.domain.entities.city import City
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
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

        self.__relationships_packages(df, package_all)

    def _progress_providers(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "Proveedores")
        providers = df["CONTRATO"].unique()
        provider_all = self.provider_repo.all()

        with self.progress("Importando proveedores", total=len(providers)):
            for provider in providers:
                provider_upper = provider.upper()
                if provider_upper not in provider_all and len(provider_all) > 0:
                    slug = self.fuzz.fuzz_property(provider_upper, provider_all)
                    if not slug:
                        slug = provider_upper
                else:
                    slug = provider_upper

                if not self.provider_repo.find_by_name(slug):
                    self.provider_repo.save(Provider(slug))
                self.progress.advance()

    def _progress_specials(self, excel):
        df = self.mega.total_dataframe(self.loader, excel, "TarifasEspeciales")
        specials = df["CONTRATO"].unique()
        special_all = self.special_repo.all()

        with self.progress("Importando tarifas especiales", total=len(specials)):
            for special in specials:
                special_upper = special.upper()
                if special_upper not in special_all and len(special_all) > 0:
                    slug = self.fuzz.fuzz_property(special_upper, special_all)
                    if not slug:
                        slug = special_upper
                else:
                    slug = special_upper

                if not self.special_repo.find_by_name(slug):
                    self.special_repo.save(Special(slug))
                self.progress.advance()

    def __relationships_rates(
        self,
        df: pl.DataFrame,
        contract_all,
    ):
        city_all = self.city_repo.all()
        activities_all = self.activity_repo.all()
        cups_all = self.cup_repo.get_all()
        df = df.fillna("")

        try:
            with self.progress("Importando tarifas", total=len(df)):
                for index, row in df.iterrows():
                    city = row["CIUDAD"].upper()
                    contract = row["CONTRATO"].upper()
                    activity = row["ACTIVIDAD"].upper()
                    cup = row["CUP"].upper()

                    contract_id = contract_all
                    city_id = city_all
                    cup_id = cups_all
                    activity_id = activities_all

                    self.progress.advance()
            pass
        except Exception as error:
            self.logger.error(f"Error saving rates: {error}", exc_info=True)
            pass
