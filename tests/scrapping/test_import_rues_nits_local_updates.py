"""Opción 1: publica el libro bd_local_actualizada (spec 016, RF-03 y RF-06)."""
import inspect
from pathlib import Path

from src.scrapping.application.use_cases.search_nits_with_odoo_fallback_use_case import (
    LOCAL_UPDATE_COLUMNS,
)
from src.scrapping.infrastructure.console import import_rues_nits
from src.scrapping.infrastructure.console.import_rues_nits import publish_local_updates
from tests.fakes.fake_findings_writer import FakeFindingsWriter


class StubUseCase:
    def __init__(self, local_updates):
        self.local_updates = local_updates


class RecordingLogger:
    def __init__(self):
        self.user_msgs = []

    def info(self, msg, *, user_msg=None, **_):
        if user_msg:
            self.user_msgs.append(user_msg)


_ROW = {"NIT": "111", "Nombre en BD local": "VIEJA", "Nombre en Odoo": "NUEVA", "Acción": "Actualizada"}


def test_publishes_bd_local_actualizada_with_columns_and_folder():
    writer, logger = FakeFindingsWriter(), RecordingLogger()

    folder = publish_local_updates(StubUseCase([_ROW]), writer, logger)

    assert folder == Path("fake")
    assert writer.books == {"bd_local_actualizada": [_ROW]}
    assert writer.columns == LOCAL_UPDATE_COLUMNS
    assert LOCAL_UPDATE_COLUMNS["bd_local_actualizada"] == [
        "NIT", "Nombre en BD local", "Nombre en Odoo", "Acción",
    ]


def test_no_book_and_sin_hallazgos_when_nothing_changed():
    writer, logger = FakeFindingsWriter(), RecordingLogger()

    folder = publish_local_updates(StubUseCase([]), writer, logger)

    assert folder is None and writer.books == {}
    assert logger.user_msgs == ["Sin hallazgos."]


def test_summary_user_msg_names_the_book_counts():
    writer, logger = FakeFindingsWriter(), RecordingLogger()

    publish_local_updates(StubUseCase([_ROW, _ROW]), writer, logger)

    assert len(logger.user_msgs) == 1
    assert "bd_local_actualizada=2" in logger.user_msgs[0]


def test_controller_publishes_in_web_scrapping_folder_and_keeps_data_json():
    """execute_web_scrapping tiene E/S real (Excel, Odoo, RUES), por eso se verifica a
    nivel de fuente, como ya hace test_import_rues_nits_wiring.py."""
    source = inspect.getsource(import_rues_nits.execute_web_scrapping)

    assert "publish_local_updates(use_case" in source
    assert 'Path("logs/web_scrapping")' in source
    assert "json.dump([d.__dict__ for d in data]" in source  # data.json con todos los resultados
