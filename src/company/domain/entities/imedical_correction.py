from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ImedicalCorrection:
    nit_error: str
    nit_success: str
    name: str
    name_error: Optional[str] = None
