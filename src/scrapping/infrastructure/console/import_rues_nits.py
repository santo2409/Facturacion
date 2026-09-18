import json
import os
from pathlib import Path

import polars as pl

from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.odooInjection.config import get_odoo_config
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (
    XmlRpcOdooRepository,
)
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.infrastructure.persistence.sa_company_nit_cache_repository import (
    SaCompanyNitCacheRepository,
)
from src.scrapping.infrastructure.reporting.not_found_companies_log_generator import (
    NotFoundCompaniesLogGenerator,
)
from src.scrapping.infrastructure.scrapers.rues_selenium_scraper import (
    RuesPlaywrightScraper,
)
from src.shared.database.database import get_session
from src.shared.utils.company_name_matcher import CompanyNameMatcher
from src.shared.utils.console import console
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller

LOGS_DIR = Path("logs")
DEFAULT_NAME_MATCH_THRESHOLD = 90
DEFAULT_RUES_NAME_LOOKUP_LIMIT = 200


def build_book_names(book_df, logger) -> dict[str, str]:
    """Mapea NIT -> razón social del libro; sin ella no hay búsqueda por nombre."""
    if "empresa" not in book_df.columns:
        logger.warning(
            "La hoja 'nits' no tiene columna 'empresa'; los pasos por nombre quedan deshabilitados",
            user_msg=(
                "La hoja 'nits' no incluye la columna 'empresa': solo se buscará por NIT. "
                "Agrega esa columna para que el sistema pueda corregir NITs errados."
            ),
        )
        return {}
    return {
        str(nit): empresa
        for nit, empresa in zip(
            book_df["nits"].to_list(), book_df["empresa"].to_list()
        )
        if empresa
    }


def execute_web_scrapping(logger):
    scraper = RuesPlaywrightScraper(logger=logger)

    config = get_odoo_config()
    odoo_repo = None
    if config["username"] and config["api_key"]:
        odoo_repo = XmlRpcOdooRepository(
            url=config["url"],
            db=config["db"],
            username=config["username"],
            api_key=config["api_key"],
            logger=logger,
            config=config,
        )

    company_repo = SaCompanyRepository(get_session(), logger)
    nit_cache_repo = SaCompanyNitCacheRepository(company_repo, logger=logger)

    name_matcher = CompanyNameMatcher(
        RapidFuzzBiller(logger),
        threshold=int(
            os.getenv("COMPANY_NAME_MATCH_THRESHOLD", str(DEFAULT_NAME_MATCH_THRESHOLD))
        ),
    )

    use_case = SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper),
        odoo_repo=odoo_repo,
        nit_cache_repo=nit_cache_repo,
        logger=logger,
        name_matcher=name_matcher,
        local_name_lookup=os.getenv("LOCAL_NAME_LOOKUP", "true").lower() != "false",
        rues_name_limit=int(
            os.getenv("RUES_NAME_LOOKUP_LIMIT", str(DEFAULT_RUES_NAME_LOOKUP_LIMIT))
        ),
    )

    route_book = os.path.join(os.getenv("BOOK_ROUTE"), os.getenv("BOOK_NAME"))
    file_path = os.path.join(os.getenv("DIRECTORY"), "data.json")

    book_df = pl.read_excel(
        route_book, sheet_name="nits", engine="calamine", infer_schema_length=0
    )
    nits = book_df.select("nits").to_series().to_list()

    book_names = build_book_names(book_df, logger)

    data = use_case.execute(nits, show_progress=True, book_names=book_names)

    NotFoundCompaniesLogGenerator(logger).generate(data, LOGS_DIR)

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump([d.__dict__ for d in data], file, ensure_ascii=False, indent=2)

    console.print(f"[green]Archivo JSON guardado en: {file_path}[/green]")
