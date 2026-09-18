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


# ── T02: similarity() ────────────────────────────────────────────────────────


def test_similarity_returns_score_between_identical_texts():
    fuzz = RapidFuzzBiller(FakeLogger())
    assert fuzz.similarity("EMPRESA A", "EMPRESA A") == 100


def test_similarity_returns_low_score_for_different_texts():
    fuzz = RapidFuzzBiller(FakeLogger())
    assert fuzz.similarity("ENTIDADES O SOCIEDADES EN EL EXTERIOR", "ACMI MEXICO") < 50


def test_similarity_returns_high_score_for_reordered_tokens():
    fuzz = RapidFuzzBiller(FakeLogger())
    score = fuzz.similarity("MARIO ALBERTO HUERTAS COTES", "HUERTAS COTES MARIO ALBERTO")
    assert score == 100


def test_similarity_returns_int():
    fuzz = RapidFuzzBiller(FakeLogger())
    assert isinstance(fuzz.similarity("A", "B"), int)


def test_similarity_returns_zero_on_error():
    fuzz = RapidFuzzBiller(FakeLogger())
    assert fuzz.similarity(None, "EMPRESA A") == 0
