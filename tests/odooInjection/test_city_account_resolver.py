from src.odooInjection.domain.services.city_account_resolver import CityAccountResolver


def test_resolve_exact_match():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve("BOGOTA")
    assert cuenta == "AA8638"
    assert score == 100


def test_resolve_exact_match_with_dc():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve("BOGOTA D.C.")
    assert cuenta == "AA8638"
    assert score == 100


def test_resolve_fuzzy_match():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve("Bogotá")
    assert cuenta == "AA8638"
    assert score == 100  # Normalización quita tildes → match exacto


def test_resolve_fuzzy_close():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve("MEDELLN")
    assert cuenta == "AA8641"
    assert score >= 80


def test_resolve_none():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve(None)
    assert cuenta == "AA8638"  # fallback
    assert match is None
    assert score == 0


def test_resolve_unknown_city():
    resolver = CityAccountResolver()
    cuenta, match, score = resolver.resolve("XYZNONEXISTENT")
    assert cuenta == "AA8638"  # fallback
    assert score == 0
