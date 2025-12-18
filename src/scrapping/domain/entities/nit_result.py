from dataclasses import dataclass


@dataclass
class NitResult:
    nit: int
    is_company: bool
    company: str | None = None
