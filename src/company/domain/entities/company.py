from dataclasses import dataclass


@dataclass
class Company:
    id: int
    nit: str
    name: str
