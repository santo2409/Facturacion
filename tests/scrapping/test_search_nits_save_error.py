"""Spec 017, T03: un fallo del guardado en lote no se reporta como nombre duplicado."""
from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    ACTION_NOT_UPDATED_ERROR,
    SAVE_ERROR,
    SearchNitsWithOdooFallbackUseCase,
)
from src.scrapping.domain.entities.nit_result import NitResult
from tests.fakes.fake_nit_cache_repo import FakeNitCacheRepo
from tests.fakes.fake_odoo_repo import FakeOdooRepo


class _NoScraper:
    def search_nits(self, nits, show_progress=False):
        return [NitResult(n, False) for n in nits]


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


def _use_case(cache, logger):
    odoo = FakeOdooRepo(clients={
        "111": {"id": 1, "name": "EMPRESA UNO"},
        "222": {"id": 2, "name": "EMPRESA DOS"},
    })
    return SearchNitsWithOdooFallbackUseCase(
        SearchNitsUseCase(_NoScraper()), odoo_repo=odoo, nit_cache_repo=cache, logger=logger
    )


def test_fallo_de_guardado_no_marca_conflicto_de_nombre():
    uc = _use_case(FakeNitCacheRepo(fail=True), RecordingLogger())

    results = uc.execute(["111", "222"])

    assert all(r.conflict == "" for r in results)
    assert all(r.save_error == SAVE_ERROR for r in results)
    assert {u["Acción"] for u in uc.local_updates} == {ACTION_NOT_UPDATED_ERROR}


def test_fallo_de_guardado_emite_un_solo_user_msg_con_n():
    logger = RecordingLogger()
    uc = _use_case(FakeNitCacheRepo(fail=True), logger)

    uc.execute(["111", "222"])

    assert len(logger.user_msgs) == 1
    assert "2" in logger.user_msgs[0]
    assert any("fallo simulado" in m for m in logger.technical)


def test_guardado_exitoso_no_marca_save_error():
    uc = _use_case(FakeNitCacheRepo(), RecordingLogger())

    results = uc.execute(["111", "222"])

    assert all(r.save_error == "" and r.conflict == "" for r in results)


def test_omitido_por_nombre_sigue_siendo_conflicto_y_no_save_error():
    uc = _use_case(FakeNitCacheRepo(omit=["222"]), RecordingLogger())

    results = {str(r.nit): r for r in uc.execute(["111", "222"])}

    assert results["222"].conflict and results["222"].save_error == ""
    assert results["111"].conflict == ""
