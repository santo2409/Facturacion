import json
import os

import polars as pl

from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.rates.domain.entities.rate import Rate
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.special.domain.entities.special import Special


class AssignRatesFromExcel:
    def __init__(
        self,
        biller_repo,
        company_repo,
        biller_company_repo,
        package_repo,
        provider_repo,
        special_repo,
        city_repo,
        activities_repo,
        rates_repo,
        cup_repo,
        nit_service,
        fuzz,
        progress,
        logger,
    ):
        self.biller_repo = biller_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.city_repo = city_repo
        self.activities_repo = activities_repo
        self.rates_repo = rates_repo
        self.cup_repo = cup_repo
        self.nit_service = nit_service
        self.fuzz = fuzz
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, excel: pl.DataFrame):
        cities_all = self.city_repo.all()
        companies_all = self.company_repo.all()
        biller_companies_all = self.biller_company_repo.all()
        billers_all = self.biller_repo.all()
        companies_rates_all = self.company_repo.companies_packages_all()
        packages_all = self.package_repo.all()
        providers_all = self.provider_repo.all()
        special_all = self.special_repo.all()
        activity_all = self.activities_repo.all()
        cup_all = self.cup_repo.get_all()

        def __is_integer_parseable(x):
            return str(x).replace("-", "").isdigit()

        def __normalize_city(x, cities_all):
            result = self.fuzz.fuzz_property(str(x).upper(), cities_all)
            return result if result is not None else str(x)

        def __match_company(nit, empresa, base, companies_all, scraped_nits):
            if nit:
                company = next((c for c in companies_all if c["nit"] == nit), None)
                if company:
                    return company["nit"], company["name"]

                scraped = next(
                    (s for s in scraped_nits if str(s.get("nit")) == nit), None
                )
                if scraped:
                    return nit, scraped.get("name") or empresa

            self.logger.warning(
                f"NIT {nit} - {empresa} no encontrado, registrado por {base}",
                user_msg=f"El NIT {nit} no fue encontrado en el sistema. Empresa registrada como {empresa} por {base}.",
            )
            return nit, empresa

        def __biller_assign(nit, companies_all, biller_companies_all, billers_all):
            company_id = next((c["id"] for c in companies_all if c["nit"] == nit), None)
            if company_id is None:
                self.logger.debug(f"NIT {nit}: empresa no encontrada → GENERAL")
                return "GENERAL"

            biller_id = next(
                (
                    bc["biller"]
                    for bc in biller_companies_all
                    if bc["company"] == company_id
                ),
                None,
            )
            if biller_id is None:
                self.logger.debug(f"NIT {nit}: company_id={company_id} sin facturador → GENERAL")
                return "GENERAL"

            biller_name = next(
                (b["name"] for b in billers_all if b["id"] == biller_id), None
            )
            result = biller_name or "GENERAL"
            self.logger.debug(f"NIT {nit}: company_id={company_id}, biller_id={biller_id} → {result}")
            return result

        def __package_assign(
            nit, companies_rates_all, companies_all, packages, providers, specials
        ):
            comp_id = next((c["id"] for c in companies_all if c["nit"] == nit), None)
            package_id, model = next(
                (
                    (c["package"], c["model"])
                    for c in companies_rates_all
                    if c["company"] == comp_id
                ),
                (None, None),
            )

            match model:
                case Package.__name__:
                    return next(
                        (c["name"] for c in packages if c["id"] == package_id), None
                    )

                case Provider.__name__:
                    return next(
                        (c["name"] for c in providers if c["id"] == package_id), None
                    )

                case Special.__name__:
                    return next(
                        (c["name"] for c in specials if c["id"] == package_id), None
                    )

                case _:
                    return next((c["name"] for c in packages if c["id"] == 30), None)

        def __rates_cup(
            nit,
            city,
            activity,
            header,
            cities_catalog,
            companies_catalog,
            companies_rates_catalog,
            activities_catalog,
            cup_catalog,
            pkg,
            packages,
        ):

            pkg_id = None
            company_id = next(
                (c["id"] for c in companies_catalog if c["nit"] == nit), None
            )
            package_id, model = next(
                (
                    (c["package"], c["model"])
                    for c in companies_rates_catalog
                    if c["company"] == company_id
                ),
                (None, None),
            )

            if package_id is None:
                package_id, model = next(
                    ((c["id"], Package.__name__) for c in packages if c["name"] == pkg),
                    (None, None),
                )

            city_id = next((c["id"] for c in cities_catalog if c["name"] == city), None)

            cup_id = next(
                (c["id"] for c in cup_catalog if c["code"].strip() == str(header).strip()), None
            )

            activity_id = next(
                (c["id"] for c in activities_catalog if c["name"] == activity), None
            )

            if not all([package_id, city_id, activity_id, model]):
                return 1

            if cup_id is None:
                return 1

            result = self.rates_repo.find_by_name(
                Rate(package_id, city_id, cup_id, 0, activity_id, model)
            )

            if result:
                price = result[3]
                return price

            return 1

        try:
            with self.progress("Importando tarifas", total=excel.height):
                df = excel

                headers = [item for item in df.columns if __is_integer_parseable(item)]

                cities_catalog = cities_all
                companies_catalog = companies_all
                companies_rates_catalog = companies_rates_all
                biller_companies_catalog = biller_companies_all
                billers_catalog = billers_all
                activities_catalog = activity_all
                cup_catalog = cup_all

                packages = packages_all
                providers = providers_all
                specials = special_all

                scraped_nits = []
                json_path = os.path.join(os.getenv("DIRECTORY", ""), "data.json")
                if os.path.exists(json_path):
                    with open(json_path, encoding="utf-8") as f:
                        scraped_nits = json.load(f)

                df = df.with_columns(
                    pl.col("Ciudad")
                    .map_elements(
                        lambda x: __normalize_city(x, cities_catalog),
                        return_dtype=pl.Utf8,
                    )
                    .alias("Ciudad")
                )

                df = df.with_columns(
                    pl.col("NIT")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.extract_all(r"\d+")
                    .list.first()
                    .str.slice(0, 9)
                    .alias("NIT")
                )

                matched_data = []
                for row in df.iter_rows(named=True):
                    nit, empresa = __match_company(
                        row["NIT"],
                        row["Empresa"],
                        row["Base"],
                        companies_catalog,
                        scraped_nits,
                    )
                    matched_data.append({"NIT": nit, "Empresa": empresa})

                matched_df = pl.DataFrame(matched_data)
                df = df.with_columns(
                    [
                        matched_df["NIT"].alias("NIT"),
                        matched_df["Empresa"].alias("Empresa"),
                    ]
                )

                df = df.with_columns(
                    pl.col("Empresa")
                    .str.to_uppercase()
                    .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                    .str.replace_all(r"\s+", " ")
                    .str.strip_chars()
                    .alias("Empresa")
                )

                df = df.with_columns(
                    pl.col("Empresa Misión")
                    .str.to_uppercase()
                    .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                    .str.replace_all(r"\s+", " ")
                    .str.strip_chars()
                    .alias("Empresa Misión")
                )

                df = df.with_columns(
                    pl.col("Sede")
                    .str.to_uppercase()
                    .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                    .str.replace_all(r"\s+", " ")
                    .str.strip_chars()
                    .alias("Sede")
                )

                df = df.with_columns(
                    pl.col("Medio de Pago")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .str.replace_all(r"\s+", " ")
                    .cast(pl.Utf8)
                    .alias("Medio de Pago")
                )

                df = df.with_columns(
                    pl.col("Tipo Examen")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .str.replace_all(r"\s+", " ")
                    .cast(pl.Utf8)
                    .alias("Tipo Examen")
                )

                df = df.with_columns(
                    pl.col("Cargo")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .str.replace_all(r"[^A-Z&Ñ#0-9\s]", "")
                    .str.replace_all(r"\s+", " ")
                    .cast(pl.Utf8)
                    .alias("Cargo")
                )

                df = df.with_columns(
                    pl.col("Paciente")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                    .str.replace_all(r"\s+", " ")
                    .cast(pl.Utf8)
                    .alias("Paciente")
                )

                df = df.with_columns(
                    pl.col("TIPO DE ACTIVIDAD")
                    .fill_null("INTRA")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .str.replace_all("INTRAMURAL", "INTRA")
                    .str.replace_all("EXTRAMURAL", "EXTRA")
                    .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                    .cast(pl.Utf8)
                    .alias("TIPO DE ACTIVIDAD")
                )

                df = df.with_columns(
                    pl.col("NIT")
                    .map_elements(
                        lambda nit: __biller_assign(
                            nit,
                            companies_catalog,
                            biller_companies_catalog,
                            billers_catalog,
                        ),
                        return_dtype=pl.Utf8,
                    )
                    .alias("FACTURADOR")
                )

                df = df.with_columns(
                    pl.when(pl.col("FACTURADOR") == "GENERAL")
                    .then(pl.lit("GENERAL"))
                    .otherwise(pl.lit("ESPECIAL"))
                    .alias("Especial / General")
                )

                df = df.with_columns(
                    pl.col("NIT")
                    .map_elements(
                        lambda nit: __package_assign(
                            nit,
                            companies_rates_catalog,
                            companies_catalog,
                            packages,
                            providers,
                            specials,
                        ),
                        return_dtype=pl.Utf8,
                    )
                    .alias("PAQUETE")
                )

                for header in headers:
                    df = df.with_columns(pl.col(str(header)).cast(pl.Int64))

                for idx, row in enumerate(df.iter_rows(named=True)):
                    nit = row["NIT"]
                    city = row["Ciudad"]
                    activity = row["TIPO DE ACTIVIDAD"]
                    pkg = row["PAQUETE"]

                    for header in headers:
                        if row.get(str(header)) == 1.0:
                            price = __rates_cup(
                                nit,
                                city,
                                activity,
                                header,
                                cities_catalog,
                                companies_catalog,
                                companies_rates_catalog,
                                activities_catalog,
                                cup_catalog,
                                pkg,
                                packages,
                            )
                            df[idx, str(header)] = int(price)

                    self.progress.advance()

                df.write_excel(
                    "CONSOLIDADO.xlsx",
                    worksheet="Consolidado",
                    table_style="Table Style Medium 2",
                )

        except Exception as error:
            self.logger.error(
                f"Error saving rates: {error}",
                exc_info=True,
                user_msg="Ocurrió un error al generar el consolidado.",
            )
