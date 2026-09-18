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
    loader.load_sheets_by_prefix.return_value = pl.DataFrame({"X": [1]})
    excel = MagicMock()

    uc.execute(excel, loader, "/tmp/output")

    pkg_normalizer.normalize.assert_called_once()
    prov_normalizer.normalize.assert_called_once()
    spec_normalizer.normalize.assert_called_once()
    exporter.export_dataframes.assert_called_once()

    # Specials should be discovered via prefix, to support multiple sheets
    loader.load_sheets_by_prefix.assert_called_once_with(excel, "TarifasEspeciales")

    # Verify the dict passed to exporter has correct keys
    call_args = exporter.export_dataframes.call_args[0]
    assert "Paquetes" in call_args[0]
    assert "Proveedores" in call_args[0]
    assert "TarifasEspeciales" in call_args[0]


def test_execute_calls_novelties_log_generator_with_combined_novelties(tmp_path):
    from src.dataProcessing.domain.entities.cup_novelty import (
        CupNovelty,
        ESTADO_CORREGIDO_NOMBRE,
        ESTADO_NO_CORREGIDO,
        FASE_NOMBRE,
    )
    from tests.fakes.fake_cup_novelties_log_generator import FakeCupNoveltiesLogGenerator

    pkg_normalizer = MagicMock()
    prov_normalizer = MagicMock()
    spec_normalizer = MagicMock()
    exporter = MagicMock()

    pkg_normalizer.normalize.return_value = pl.DataFrame({"A": [1]})
    prov_normalizer.normalize.return_value = pl.DataFrame({"B": [2]})
    spec_normalizer.normalize.return_value = pl.DataFrame({"C": [3]})

    n1 = CupNovelty(hoja="Paquetes", cup_original="1", examen="E", cup_corregido="2",
                     detalle="", estado=ESTADO_CORREGIDO_NOMBRE, fase=FASE_NOMBRE)
    n2 = CupNovelty(hoja="Proveedores", cup_original="3", examen="E2", cup_corregido=None,
                     detalle="", estado=ESTADO_NO_CORREGIDO, fase="")
    pkg_normalizer.novelties = [n1]
    prov_normalizer.novelties = [n2]
    spec_normalizer.novelties = []

    log_generator = FakeCupNoveltiesLogGenerator()

    uc = NormalizeInformationFromExcel(
        pkg_normalizer, prov_normalizer, spec_normalizer, exporter,
        novelties_log_generator=log_generator, logs_dir=tmp_path,
    )

    loader = MagicMock()
    loader.load_sheet.return_value = pl.DataFrame({"X": [1]})
    loader.load_sheets_by_prefix.return_value = pl.DataFrame({"X": [1]})
    excel = MagicMock()

    uc.execute(excel, loader, "/tmp/output")

    assert len(log_generator.calls) == 1
    novelties_arg, output_dir_arg = log_generator.calls[0]
    assert novelties_arg == [n1, n2]
    assert output_dir_arg == tmp_path


def test_execute_without_log_generator_skips_report():
    pkg_normalizer = MagicMock()
    prov_normalizer = MagicMock()
    spec_normalizer = MagicMock()
    exporter = MagicMock()

    pkg_normalizer.normalize.return_value = pl.DataFrame({"A": [1]})
    prov_normalizer.normalize.return_value = pl.DataFrame({"B": [2]})
    spec_normalizer.normalize.return_value = pl.DataFrame({"C": [3]})
    pkg_normalizer.novelties = []
    prov_normalizer.novelties = []
    spec_normalizer.novelties = []

    uc = NormalizeInformationFromExcel(pkg_normalizer, prov_normalizer, spec_normalizer, exporter)

    loader = MagicMock()
    loader.load_sheet.return_value = pl.DataFrame({"X": [1]})
    loader.load_sheets_by_prefix.return_value = pl.DataFrame({"X": [1]})
    excel = MagicMock()

    # No debe lanzar ninguna excepción aunque no haya log generator inyectado
    uc.execute(excel, loader, "/tmp/output")
