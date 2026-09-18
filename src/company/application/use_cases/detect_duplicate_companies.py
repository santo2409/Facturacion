from pathlib import Path

from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter


class DetectDuplicateCompanies:
    """Barre la tabla `companies` completa y reporta candidatos a empresa
    duplicada para revisión manual. No escribe en la base de datos."""

    def __init__(self, company_repo, detector, log_generator, progress, logger=None):
        self.company_repo = company_repo
        self.detector = detector
        self.log_generator = log_generator
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)

    def execute(self, output_dir: Path) -> Path:
        with self.progress("Analizando empresas", total=1):
            companies = self.company_repo.all() or []
            self.progress.advance()

        candidates = self.detector.detect(companies)

        self.logger.info(
            f"Detección de duplicados: {len(candidates)} candidato(s) sobre "
            f"{len(companies)} empresas",
            user_msg=(
                f"{len(candidates)} posible(s) empresa(s) duplicada(s) encontrada(s) "
                f"sobre {len(companies)} registradas; revisa empresas_duplicadas.xlsx."
                if candidates
                else f"No se encontraron empresas duplicadas sobre {len(companies)} registradas."
            ),
        )

        return self.log_generator.generate(candidates, output_dir)
