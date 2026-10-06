from dataclasses import dataclass


@dataclass(frozen=True)
class TianAssignment:
    nit_original: str
    name_original: str
    nit_tian: str
    name_final: str
    rows: int = 1
