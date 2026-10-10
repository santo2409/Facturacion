from pathlib import Path

from src.assign.domain.repositories.phase_findings_reporter import PhaseFindingsReporter


class FakePhaseFindingsReporter(PhaseFindingsReporter):
    def __init__(self):
        self.findings: dict[str, list[dict]] | None = None
        self.companies: list[dict] | None = None

    def write(self, findings, companies):
        self.findings = {k: v for k, v in findings.items() if v}
        self.companies = companies
        return Path("fake")
