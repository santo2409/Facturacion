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
