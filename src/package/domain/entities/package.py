from dataclasses import dataclass
from typing import Optional


@dataclass
class Package:
    name: str
    id: Optional[int] = None
