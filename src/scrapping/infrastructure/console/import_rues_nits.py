import json
import os

import polars as pl

from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.infrastructure.scrapers.datos_gov_scraper import DatosGovScraper
from src.shared.utils.console import console


def execute_web_scrapping():
    scraper = DatosGovScraper()
    use_case = SearchNitsUseCase(scraper)

    route_book = os.path.join(os.getenv("BOOK_ROUTE"), os.getenv("BOOK_NAME"))
    file_path = os.path.join(os.getenv("DIRECTORY"), "data.json")

    nits = (
        pl.read_excel(
            route_book, sheet_name="nits", engine="calamine", infer_schema_length=0
        )
        .select("nits")
        .to_series()
        .to_list()
    )

    data = use_case.execute(nits, show_progress=True)

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump([d.__dict__ for d in data], file, ensure_ascii=False, indent=2)

    console.print(f"[green]Archivo JSON guardado en: {file_path}[/green]")
