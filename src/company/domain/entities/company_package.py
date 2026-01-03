from dataclasses import dataclass


@dataclass
class CompanyPackage:
    company_id: int
    package_id: int
    model: str
