"""Spec 018: el aviso de corrección solo remite al libro cuando el libro lista la empresa."""
import openpyxl

from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.reporting.not_found_companies_log_generator import (
    NotFoundCompaniesLogGenerator,
)
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo

_NOTICE = "empresas_no_encontradas.xlsx"


class RecordingLogger:
    """Doble local: FakeLogger no captura user_msg."""

    def __init__(self):
        self.user_msgs = []
        self.technical = []

    def _log(self, msg, user_msg=None, **_):
        self.technical.append(msg)
        if user_msg:
            self.user_msgs.append(user_msg)

    info = warning = error = _log


class _Scraper:
    def __init__(self, results=None):
        self._results = results or {}

    def search_nits(self, nits, show_progress=False):
        return [self._results.get(str(n), NitResult(n, False)) for n in nits]


def _notices(logger):
    return [m for m in logger.user_msgs if _NOTICE in m]


def _use_case(logger, scraper=None, odoo=None, cache=None):
    return SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(scraper or _Scraper()),
        odoo_repo=odoo,
        nit_cache_repo=cache,
        logger=logger,
    )


def test_resuelta_en_odoo_no_emite_aviso():
    logger = RecordingLogger()
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "NOMBRE EN ODOO"}})
    uc = _use_case(logger, odoo=odoo)

    result = uc.execute(["111"], book_names={"111": "NOMBRE DEL LIBRO"})

    assert result[0].checked_bases == "Odoo"
    assert _notices(logger) == []
    assert any("[NOVEDAD]" in m for m in logger.technical)


def test_resuelta_en_bd_local_no_emite_aviso():
    logger = RecordingLogger()
    cache = FakeNitCacheRepo(cached={"111": NitResult("111", True, "NOMBRE LOCAL", "BD local")})
    uc = _use_case(logger, cache=cache)

    result = uc.execute(["111"], book_names={"111": "NOMBRE DEL LIBRO"})

    assert result[0].checked_bases == "BD local"
    assert _notices(logger) == []
    assert any("[NOVEDAD]" in m for m in logger.technical)


def test_solo_en_rues_emite_aviso_y_aparece_en_el_libro(tmp_path):
    logger = RecordingLogger()
    scraper = _Scraper({"111": NitResult("111", True, "NOMBRE EN RUES")})
    uc = _use_case(logger, scraper=scraper, odoo=FakeOdooRepo())

    result = uc.execute(["111"], book_names={"111": "NOMBRE DEL LIBRO"})

    assert result[0].checked_bases == "Odoo, RUES"
    assert len(_notices(logger)) == 1
    assert "NOMBRE EN RUES" in _notices(logger)[0]

    log_path = NotFoundCompaniesLogGenerator(FakeLogger()).generate(result, tmp_path)
    ws = openpyxl.load_workbook(log_path, data_only=True).active
    nits = [r[1] for r in ws.iter_rows(min_row=2, values_only=True) if r and r[1]]
    assert nits == ["111"]


def test_sin_correccion_no_emite_aviso():
    logger = RecordingLogger()
    scraper = _Scraper({"111": NitResult("111", True, "MISMO NOMBRE")})
    uc = _use_case(logger, scraper=scraper, odoo=FakeOdooRepo())

    uc.execute(["111"], book_names={"111": "MISMO NOMBRE"})

    assert _notices(logger) == []
    assert not any("[NOVEDAD]" in m for m in logger.technical)


def test_el_resultado_conserva_nit_original_y_name_original():
    odoo = FakeOdooRepo(clients={"111": {"id": 1, "name": "NOMBRE EN ODOO"}})
    scraper = _Scraper({"222": NitResult("222", True, "NOMBRE EN RUES")})

    en_odoo = _use_case(RecordingLogger(), odoo=odoo).execute(
        ["111"], book_names={"111": "NOMBRE DEL LIBRO"}
    )[0]
    en_rues = _use_case(RecordingLogger(), scraper=scraper, odoo=FakeOdooRepo()).execute(
        ["222"], book_names={"222": "OTRO NOMBRE DEL LIBRO"}
    )[0]

    assert en_odoo.name_original == "NOMBRE DEL LIBRO" and en_odoo.nit_original is None
    assert en_rues.name_original == "OTRO NOMBRE DEL LIBRO" and en_rues.nit_original is None
