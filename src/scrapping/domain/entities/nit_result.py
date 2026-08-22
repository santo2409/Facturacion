from dataclasses import dataclass


@dataclass
class NitResult:
    nit: int
    is_company: bool
    name: str | None = None
    checked_bases: str = ""
