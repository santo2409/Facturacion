"""Tests para el controller de la opción 5 (spec 007, RF-08). Sigue el
patrón de pre_invoice_controller.py: sesión abierta fuera del try, error
contenido con logging dual sin re-lanzar, sesión cerrada en finally."""

import src.company.infrastructure.console.import_companies_rates_controller as controller
from tests.fakes.fake_logger import FakeLogger


class CapturingLogger(FakeLogger):
    """FakeLogger descarta los kwargs (`def error(self, msg, **_)`), así que
    las cláusulas del AC sobre "traza técnica y mensaje al usuario" no serían
    verificables con él."""

    def __init__(self):
        super().__init__()
        self.error_kwargs = []

    def error(self, msg, **kwargs):
        super().error(msg, **kwargs)
        self.error_kwargs.append(kwargs)


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _RaisingUseCase:
    def execute(self, df):
        raise RuntimeError("fallo simulado en el caso de uso")


class _SucceedingUseCase:
    def __init__(self):
        self.executed_with = None

    def execute(self, df):
        self.executed_with = df


def test_import_companies_error_en_use_case_no_se_propaga_y_cierra_sesion(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(controller, "_load_dataframe", lambda: "df-dummy")
    monkeypatch.setattr(controller, "get_session", lambda: session)
    monkeypatch.setattr(controller, "_build_use_case", lambda s, l: _RaisingUseCase())
    logger = CapturingLogger()

    controller.import_companies(logger)  # no debe propagar RuntimeError

    assert session.closed is True
    assert logger.errors
    # "el error se registra con traza técnica Y mensaje al usuario"
    assert "fallo simulado en el caso de uso" in logger.errors[0]
    assert logger.error_kwargs[0]["exc_info"] is True
    assert logger.error_kwargs[0]["user_msg"]


def test_import_companies_exito_tambien_cierra_sesion(monkeypatch):
    session = FakeSession()
    use_case = _SucceedingUseCase()
    monkeypatch.setattr(controller, "_load_dataframe", lambda: "df-dummy")
    monkeypatch.setattr(controller, "get_session", lambda: session)
    monkeypatch.setattr(controller, "_build_use_case", lambda s, l: use_case)
    logger = FakeLogger()

    controller.import_companies(logger)

    assert session.closed is True
    assert use_case.executed_with == "df-dummy"
    assert not logger.errors


def test_build_use_case_wires_findings_writer_for_registrar_empresas():
    """spec 011, RF-06: los hallazgos de la opción 5 salen en libros por ejecución."""
    from pathlib import Path

    from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter

    use_case = controller._build_use_case(object(), FakeLogger())

    assert isinstance(use_case.findings_writer, XlsxFindingsWriter)
    assert use_case.findings_writer._base_dir == Path("logs/registrar_empresas")


def test_build_use_case_injects_rues_cache_loader_for_registrar_empresas():
    """spec 016: data.json solo aporta resultados de RUES; Odoo se consulta siempre."""
    from src.scrapping.infrastructure.persistence.rues_json_cache import load_rues_cache

    use_case = controller._build_use_case(object(), FakeLogger())

    assert use_case.rues_cache_loader is load_rues_cache
