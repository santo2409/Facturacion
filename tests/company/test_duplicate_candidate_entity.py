from src.company.domain.entities.duplicate_candidate import DuplicateCandidate


def test_duplicate_candidate_creation():
    c = DuplicateCandidate(
        nit_a="83004087",
        name_a="ACTIVIDADES DE INSTALACIONES Y SERVICIOS COBRA S.A",
        nit_b="830040872",
        name_b="ACTIVIDADES DE INSTALACIONES Y SERVICIOS COBRA S A",
        reasons=["Nombre idéntico (ignorando puntuación y espacios)"],
        similarity=97,
    )
    assert c.nit_a == "83004087"
    assert c.nit_b == "830040872"
    assert c.reasons == ["Nombre idéntico (ignorando puntuación y espacios)"]
    assert c.similarity == 97


def test_duplicate_candidate_supports_multiple_reasons():
    c = DuplicateCandidate(
        nit_a="83004087", name_a="A", nit_b="830040872", name_b="B",
        reasons=["Nombre idéntico (ignorando puntuación y espacios)", "NIT difiere en el dígito final"],
        similarity=97,
    )
    assert len(c.reasons) == 2
