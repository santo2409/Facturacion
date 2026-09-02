"""Tests para ask_excel_path - validar el texto de prompt mostrado."""
from unittest.mock import patch

from src.shared.console.file_input import ask_excel_path


def test_ask_excel_path_uses_default_label(tmp_path):
    file = tmp_path / "archivo.xlsx"
    file.touch()

    with patch("src.shared.console.file_input.Prompt.ask", return_value=str(file)) as mock_ask:
        result = ask_excel_path()

    mock_ask.assert_called_once_with("Ruta completa del archivo Excel")
    assert result == file


def test_ask_excel_path_uses_custom_label(tmp_path):
    file = tmp_path / "archivo.xlsx"
    file.touch()

    with patch("src.shared.console.file_input.Prompt.ask", return_value=str(file)) as mock_ask:
        result = ask_excel_path("Ruta del Excel con NÚMEROS DE FACTURA")

    mock_ask.assert_called_once_with("Ruta del Excel con NÚMEROS DE FACTURA")
    assert result == file
