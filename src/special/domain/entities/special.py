from dataclasses import dataclass
from typing import Optional


@dataclass
class Special:
    name: str
    id: Optional[int] = None
