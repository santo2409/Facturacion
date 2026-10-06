from src.shared.utils.company_name_matcher import CompanyNameMatcher
from tests.fakes.fake_fuzz import FakeFuzz


class RecordingFuzz:
    """Fake que registra los argumentos recibidos por fuzz_property."""

    def __init__(self, result=None):
        self._result = result
        self.calls = []

    def fuzz_property(self, name, catalog, threshold=90):
        self.calls.append({"name": name, "catalog": catalog, "threshold": threshold})
        return self._result


def test_best_match_returns_full_candidate_with_id_and_vat():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 7, "name": "EMPRESA A SAS", "vat": "900111111"}]

    assert matcher.best_match("EMPRESA A SAS", candidates) == candidates[0]


def test_best_match_normalizes_accents_on_both_sides():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 1, "name": "CLINICA X SAS", "vat": "900222222"}]

    assert matcher.best_match("Clínica X S.A.S.", candidates)["id"] == 1


def test_best_match_normalizes_punctuation_and_spacing():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 2, "name": "EMPRESA A SAS", "vat": "900333333"}]

    assert matcher.best_match("  Empresa A,  S.A.S.  ", candidates)["id"] == 2


def test_best_match_returns_none_when_no_candidate_matches():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 1, "name": "OTRA COSA", "vat": "900333333"}]

    assert matcher.best_match("EMPRESA A SAS", candidates) is None


def test_best_match_returns_none_with_empty_candidates():
    assert CompanyNameMatcher(FakeFuzz()).best_match("EMPRESA A", []) is None


def test_best_match_returns_none_with_empty_expected_name():
    candidates = [{"id": 1, "name": "EMPRESA A", "vat": "900111111"}]

    assert CompanyNameMatcher(FakeFuzz()).best_match("", candidates) is None


def test_best_match_returns_none_when_fuzz_returns_none():
    """fuzz_property traga excepciones y devuelve None implícito: fail-closed."""
    matcher = CompanyNameMatcher(RecordingFuzz(result=None))
    candidates = [{"id": 1, "name": "EMPRESA A SAS", "vat": "900111111"}]

    assert matcher.best_match("EMPRESA A SAS", candidates) is None


def test_best_match_returns_none_when_fuzz_returns_unknown_name():
    matcher = CompanyNameMatcher(RecordingFuzz(result="NOMBRE QUE NO ESTA"))
    candidates = [{"id": 1, "name": "EMPRESA A SAS", "vat": "900111111"}]

    assert matcher.best_match("EMPRESA A SAS", candidates) is None


def test_best_match_first_wins_on_duplicate_names():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [
        {"id": 1, "name": "EMPRESA A", "vat": "900111111"},
        {"id": 2, "name": "EMPRESA A", "vat": "900222222"},
    ]

    assert matcher.best_match("EMPRESA A", candidates)["id"] == 1


def test_best_match_skips_candidates_without_name():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 1, "name": "", "vat": "900111111"}]

    assert matcher.best_match("EMPRESA A", candidates) is None


def test_best_match_forwards_configured_threshold():
    fuzz = RecordingFuzz(result=None)
    matcher = CompanyNameMatcher(fuzz, threshold=95)
    matcher.best_match("EMPRESA A", [{"id": 1, "name": "EMPRESA A", "vat": "900111111"}])

    assert fuzz.calls[0]["threshold"] == 95


def test_best_match_sends_normalized_names_to_fuzz():
    fuzz = RecordingFuzz(result=None)
    CompanyNameMatcher(fuzz).best_match(
        "Clínica X S.A.S.", [{"id": 1, "name": "Clínica X S.A.S.", "vat": "900111111"}]
    )

    assert fuzz.calls[0]["name"] == "CLINICA X SAS"
    assert fuzz.calls[0]["catalog"] == [{"name": "CLINICA X SAS"}]


def test_best_match_supports_custom_name_key():
    matcher = CompanyNameMatcher(FakeFuzz())
    candidates = [{"id": 1, "razon_social": "EMPRESA A", "vat": "900111111"}]

    result = matcher.best_match("EMPRESA A", candidates, name_key="razon_social")

    assert result["id"] == 1
