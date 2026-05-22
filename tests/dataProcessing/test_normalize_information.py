"""Tests para NormalizeInformationFromExcel."""
import polars as pl
from unittest.mock import MagicMock

from src.dataProcessing.application.use_cases.normalize_information_from_excel import NormalizeInformationFromExcel


def test_execute_calls_all_normalizers_and_exports():
    pkg_normalizer = MagicMock()
    prov_normalizer = MagicMock()
    spec_normalizer = MagicMock()
    exporter = MagicMock()

    pkg_normalizer.normalize.return_value = pl.DataFrame({"A": [1]})
    prov_normalizer.normalize.return_value = pl.DataFrame({"B": [2]})
    spec_normalizer.normalize.return_value = pl.DataFrame({"C": [3]})

    uc = NormalizeInformationFromExcel(pkg_normalizer, prov_normalizer, spec_normalizer, exporter)

    loader = MagicMock()
    loader.load_sheet.return_value = pl.DataFrame({"X": [1]})
    excel = MagicMock()

    uc.execute(excel, loader, "/tmp/output")

    pkg_normalizer.normalize.assert_called_once()
    prov_normalizer.normalize.assert_called_once()
    spec_normalizer.normalize.assert_called_once()
    exporter.export_dataframes.assert_called_once()

    # Verify the dict passed to exporter has correct keys
    call_args = exporter.export_dataframes.call_args[0]
    assert "Paquetes" in call_args[0]
    assert "Proveedores" in call_args[0]
    assert "TarifasEspeciales" in call_args[0]
