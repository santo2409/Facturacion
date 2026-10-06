from pathlib import Path

from src.company.application.use_cases.detect_duplicate_companies import (
    DetectDuplicateCompanies,
)
from src.company.domain.services.duplicate_company_detector import DuplicateCompanyDetector
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from src.company.infrastructure.reporting.duplicate_companies_log_generator import (
    DuplicateCompaniesLogGenerator,
)
from src.shared.console.progress import RichProgress
from src.shared.database.database import get_session
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller

LOGS_DIR = Path("logs")


def detect_duplicate_companies(logger):
    company_repo = SaCompanyRepository(get_session(), logger)

    use_case = DetectDuplicateCompanies(
        company_repo=company_repo,
        detector=DuplicateCompanyDetector(RapidFuzzBiller(logger)),
        log_generator=DuplicateCompaniesLogGenerator(logger),
        progress=RichProgress(),
        logger=logger,
    )

    use_case.execute(LOGS_DIR)
