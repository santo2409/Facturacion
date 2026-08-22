from dataclasses import dataclass


@dataclass
class Company:
    nit: str
    name: str

    def __post_init__(self):
        if self.nit is not None:
            self.nit = str(self.nit)
