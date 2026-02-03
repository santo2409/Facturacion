from dataclasses import dataclass
from typing import Optional


@dataclass
class Provider:
    name: str
    id: Optional[int] = None
