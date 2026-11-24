"""Código muerto eliminado (spec 014): ninguno de estos módulos tenía importadores."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_DEAD_MODULES = {
    "src.package.infrastructure.persistence.mysql_package_repository": ("mysql_package_repository", "MySQLPackageRepository"),
    "src.package.infrastructure.persistence.pg_package_repository": ("pg_package_repository", "PgPackageRepository"),
    "src.package.application.use_cases.update_package": ("update_package", "UpdatePackageUseCase"),
    "src.scrapping.infrastructure.scrapers.datos_gov_scraper": ("datos_gov_scraper", "DatosGovScraper"),
    "src.shared.logging.infrastructure.repositories.iLogger": ("iLogger",),
    # Opciones del menú en desuso eliminadas (antes 3, 4, 5 y 9) y lo que solo ellas usaban.
    "src.dataProcessing.infrastructure.console.import_information_controller": ("import_information_controller",),
    "src.dataProcessing.application.use_cases.normalize_information_from_excel": ("normalize_information_from_excel",),
    "src.dataProcessing.infrastructure.persistence.cup_column_validator": ("cup_column_validator",),
    "src.dataProcessing.domain.services.cup_resolver": ("cup_resolver",),
    "src.rates.infrastructure.console.import_rates_controller": ("import_rates_controller",),
    "src.rates.application.use_cases.import_rates_from_excel": ("import_rates_from_excel",),
    "src.company.infrastructure.console.import_companies_rates_controller": ("import_companies_rates_controller",),
    "src.company.application.use_cases.import_companies_from_excel": ("import_companies_from_excel",),
    "src.company.infrastructure.reporting.not_linked_companies_log_generator": ("not_linked_companies_log_generator",),
    "src.assign.infrastructure.console.missing_rates_controller": ("missing_rates_controller",),
    "src.assign.application.use_cases.missing_rates": ("generate_missing_rates",),
    "src.shared.utils.mega_dataframes": ("mega_dataframes",),
    "src.shared.utils.document_normalizer": ("document_normalizer",),
    "src.shared.excel.excel_exporter": ("excel_exporter",),
    "src.shared.console.file_output": ("ask_directory_path",),
    "src.shared.utils.deprecated": ("DEPRECATED_LABEL", "is_deprecated"),
    # Flujo viejo de inyección, reemplazado por la integración de ETL-Avancys (opción 5).
    "src.odooInjection.application.use_cases.inject_invoices_to_odoo": ("InjectInvoicesToOdoo",),
    "src.odooInjection.infrastructure.persistence.excel_pre_invoice_reader": ("ExcelPreInvoiceReader",),
    "src.odooInjection.domain.services.city_account_resolver": ("CityAccountResolver",),
    "src.odooInjection.domain.entities.city_account_map": ("city_account_map",),
    "src.odooInjection.infrastructure.reporting.excel_log_generator": ("ExcelLogGenerator",),
    "src.odooInjection.infrastructure.console.inject_invoices_controller": ("inject_invoices_controller",),
    "src.odooInjection.domain.entities.invoice_result": ("InvoiceResult",),
    "src.odooInjection.domain.repositories.pre_invoice_reader_repository": ("PreInvoiceReaderRepository",),
    "src.odooInjection.domain.entities.invoice_line": ("InvoiceLine",),
    # Detección de empresas duplicadas (antigua opción 6), eliminada el 2026-11-24.
    "src.company.application.use_cases.detect_duplicate_companies": ("DetectDuplicateCompanies",),
    "src.company.domain.services.duplicate_company_detector": ("DuplicateCompanyDetector",),
    "src.company.domain.entities.duplicate_candidate": ("DuplicateCandidate",),
    "src.company.infrastructure.console.detect_duplicates_controller": ("detect_duplicate_companies",),
    "src.company.infrastructure.reporting.duplicate_companies_log_generator": ("DuplicateCompaniesLogGenerator",),
}


@pytest.mark.parametrize("module", list(_DEAD_MODULES))
def test_dead_module_is_gone(module):
    try:
        spec = importlib.util.find_spec(module)
    except ModuleNotFoundError:  # el paquete padre ya no existe
        spec = None

    assert spec is None


def test_no_references_left_in_code():
    names = sorted({name for group in _DEAD_MODULES.values() for name in group})
    files = [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("tests").rglob("*.py"), ROOT / "main.py"]
    offenders = [
        f"{path.relative_to(ROOT)}: {name}"
        for path in files
        if path != Path(__file__).resolve()
        for name in names
        if name in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_docs_do_not_present_datos_gov_scraper_as_existing():
    assert "DatosGovScraper" not in _read("docs/c4-diagrams.md")

    technical_lines = [
        l for l in _read("docs/TECHNICAL_DOCUMENTATION.md").splitlines()
        if "DatosGovScraper" in l or "datos_gov_scraper" in l
    ]
    assert technical_lines and all("spec 014" in l for l in technical_lines)

    adr = _read("docs/adr/ADR-004-playwright-web-scraping.md")
    assert "spec 014" in adr and "datos_gov_scraper.py" in adr  # el texto original se conserva como historia
