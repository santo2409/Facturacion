"""Controller de la opción 7 cuando no existe CONSOLIDADO.xlsx (AUD-55)."""

from src.preInvoice.infrastructure.console import pre_invoice_controller as controller


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message, exc_info=None, *, user_msg=None):
        self.errors.append((message, user_msg))


def test_pre_invoice_without_consolidado_warns_once_without_markup(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(controller, "get_session", lambda: (_ for _ in ()).throw(AssertionError("no debe abrir sesión")))
    logger = _Logger()

    controller.generate_pre_invoices(logger)

    out = capsys.readouterr().out
    assert "Archivo CONSOLIDADO.xlsx no encontrado. No se pueden generar pre-facturas." in out
    assert "[red]" not in out and "[/red]" not in out
    assert logger.errors == [(
        "Archivo CONSOLIDADO.xlsx no encontrado tras assign_rates.",
        "No se encontró el archivo CONSOLIDADO.xlsx. El proceso de asignación pudo haber fallado.",
    )]
    assert not (tmp_path / "pre-facturas").exists()


class _UserLogger:
    def __init__(self):
        self.user_msgs = []

    def _log(self, level, user_msg):
        if user_msg:
            self.user_msgs.append((level, user_msg))

    def info(self, message, *, user_msg=None):
        self._log("INFO", user_msg)

    def warning(self, message, *, user_msg=None):
        self._log("WARNING", user_msg)

    def error(self, message, exc_info=None, *, user_msg=None):
        self._log("ERROR", user_msg)


class _Session:
    def close(self):
        pass


def _run_with_result(tmp_path, monkeypatch, result):
    from src.preInvoice.application.use_cases.split_by_nit import SplitResult

    monkeypatch.chdir(tmp_path)
    (tmp_path / "CONSOLIDADO.xlsx").write_bytes(b"")
    monkeypatch.setattr(controller, "get_session", lambda: _Session())
    monkeypatch.setattr(controller, "SaCupRepository", lambda session: None)
    monkeypatch.setattr(controller, "RichProgress", lambda: None)

    class _Split:
        def __init__(self, *a):
            pass

        def execute(self, *a):
            return SplitResult(*result)

    monkeypatch.setattr(controller, "SplitByNit", _Split)
    logger = _UserLogger()
    controller.generate_pre_invoices(logger)
    return logger.user_msgs


def test_pre_invoice_success_message_when_no_failures(tmp_path, monkeypatch):
    msgs = _run_with_result(tmp_path, monkeypatch, ([], []))
    assert msgs[-1] == ("INFO", "Pre-facturas generadas exitosamente.")


def test_pre_invoice_warns_with_counts_when_some_nit_failed(tmp_path, monkeypatch):
    msgs = _run_with_result(tmp_path, monkeypatch, (["900111111", "900222222"], ["900222222"]))
    assert msgs[-1] == (
        "WARNING",
        "Pre-facturas generadas con errores: 2 pre-factura(s) y 1 hoja(s) del consolidado no se generaron. "
        "Revisa logs.log.",
    )
    assert all("exitosamente" not in m for _, m in msgs)
