from dataclasses import dataclass, field


@dataclass
class DuplicateCandidate:
    """Par de empresas con NITs distintos que podrían ser la misma entidad.

    `nit_a`/`nit_b` van siempre ordenados por quien construye el candidato,
    de modo que un mismo par se identifique de forma única sin importar en
    qué orden se descubrió.
    """

    nit_a: str
    name_a: str
    nit_b: str
    name_b: str
    reasons: list[str] = field(default_factory=list)
    similarity: int = 0
