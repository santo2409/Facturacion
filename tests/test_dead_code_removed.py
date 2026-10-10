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
