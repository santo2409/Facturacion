from dataclasses import dataclass


@dataclass
class UnlinkedRow:
    document: str
    company_name: str
    package: str
    reason: str
