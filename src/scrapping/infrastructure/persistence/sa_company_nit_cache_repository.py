from src.company.domain.entities.company import Company
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.repositories.nit_cache_repository import NitCacheRepository
from src.shared.utils.text_normalizer import normalize_nit


class SaCompanyNitCacheRepository(NitCacheRepository):
    """Adapta la tabla `companies` (vía CompanyRepository) como caché de
    NITs ya verificados. Es 'best effort': si la tabla está vacía o el
    repo falla, get_many() retorna {} y el flujo sigue a Odoo/RUES."""

    def __init__(self, company_repo, logger=None):
        self._company_repo = company_repo
        self._logger = logger

    def get_many(self, nits: list[str]) -> dict[str, NitResult]:
        try:
            rows = self._company_repo.all() or []
        except Exception:
            return {}
        wanted = {normalize_nit(str(n)): str(n) for n in nits}
        found: dict[str, NitResult] = {}
        for r in rows:
            original = wanted.get(r["nit"])
            if original:
                found[original] = NitResult(
                    nit=r["nit"], is_company=True, name=r["name"], checked_bases="BD local"
                )
        return found

    def save_many(self, results: list[NitResult]) -> None:
        positives = [
            Company(normalize_nit(str(r.nit)), r.name)
            for r in results if r.is_company and r.name
        ]
        if not positives:
            return
        try:
            self._company_repo.save_batch(positives)
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Fallo guardando caché local de NITs: {e}")
