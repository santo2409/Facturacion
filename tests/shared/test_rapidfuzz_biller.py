from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from tests.fakes.fake_logger import FakeLogger


def test_fuzz_exact_match():
    fuzz = RapidFuzzBiller(FakeLogger())
    catalog = [{"name": "FACTURADOR ALFA"}, {"name": "FACTURADOR BETA"}]
    result = fuzz.fuzz_property("FACTURADOR ALFA", catalog)
    assert result == "FACTURADOR ALFA"


def test_fuzz_partial_match():
    fuzz = RapidFuzzBiller(FakeLogger())
    catalog = [{"name": "FACTURADOR ALFA"}, {"name": "FACTURADOR BETA"}]
    result = fuzz.fuzz_property("FACTURADOR  ALFA", catalog)
    assert result == "FACTURADOR ALFA"


def test_fuzz_no_match():
    fuzz = RapidFuzzBiller(FakeLogger())
    catalog = [{"name": "FACTURADOR ALFA"}]
    result = fuzz.fuzz_property("COMPLETAMENTE DIFERENTE XYZ", catalog, threshold=95)
    assert result is None


def test_fuzz_threshold():
    fuzz = RapidFuzzBiller(FakeLogger())
    catalog = [{"name": "BOGOTA"}]
    # Close enough at 90
    result = fuzz.fuzz_property("BOGOT", catalog, threshold=80)
    assert result == "BOGOTA"


def test_fuzz_empty_catalog():
    fuzz = RapidFuzzBiller(FakeLogger())
    # extractOne raises on empty list
    result = fuzz.fuzz_property("TEST", [])
    assert result is None
