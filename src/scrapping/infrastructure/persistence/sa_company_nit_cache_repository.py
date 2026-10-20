from src.company.domain.entities.company import Company
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.domain.exceptions import NitCacheSaveError
from src.scrapping.domain.repositories.nit_cache_repository import NitCacheRepository
from src.shared.utils.text_normalizer import normalize_company_name, normalize_nit


class SaCompanyNitCacheRepository(NitCacheRepository):
    """Adapta la tabla `companies` (vía CompanyRepository) como caché de
    NITs ya verificados. Es 'best effort': si la tabla está vacía o el
    repo falla, las consultas retornan {} y el flujo sigue a Odoo/RUES."""

    def __init__(self, company_repo, logger=None):
        self._company_repo = company_repo
        self._logger = logger
        self._by_nit: dict[str, dict] | None = None
        self._by_name: dict[str, dict] | None = None

    def _load_indexes(self) -> None:
        """Construye los índices por NIT y por nombre en una sola lectura."""
        if self._by_nit is not None:
            return
        try:
            rows = self._company_repo.all() or []
        except Exception:
            rows = []

        by_nit: dict[str, dict] = {}
        by_name: dict[str, dict] = {}
        for row in rows:
            by_nit.setdefault(normalize_nit(str(row["nit"])), row)
            name_key = normalize_company_name(row["name"])
            if name_key:
                by_name.setdefault(name_key, row)
        self._by_nit, self._by_name = by_nit, by_name

    @staticmethod
    def _to_result(row: dict, source: str) -> NitResult:
        return NitResult(
            nit=row["nit"],
            is_company=True,
            name=row["name"],
            checked_bases="BD local",
            source=source,
        )

    def get_many(self, nits: list[str]) -> dict[str, NitResult]:
        self._load_indexes()
        found: dict[str, NitResult] = {}
        for nit in nits:
            row = self._by_nit.get(normalize_nit(str(nit)))
            if row:
                found[str(nit)] = self._to_result(row, "BD local/NIT")
        return found

    def get_by_names(self, names: list[str]) -> dict[str, NitResult]:
        self._load_indexes()
        found: dict[str, NitResult] = {}
        for name in names:
            row = self._by_name.get(normalize_company_name(name))
            if row:
                found[name] = self._to_result(row, "BD local/nombre")
        return found

    @staticmethod
    def _dedupe_by_normalized_nit(results: list[NitResult]) -> list[Company]:
        """Un solo Company por NIT normalizado: el de fuente Odoo si lo hay, si
        no el primero. Evita enviar el mismo NIT dos veces al INSERT en lote."""
        chosen: dict[str, NitResult] = {}
        for r in results:
            if not (r.is_company and r.name):
                continue
            norm = normalize_nit(str(r.nit))
            current = chosen.get(norm)
            if current is None or (
                str(r.source).startswith("Odoo") and not str(current.source).startswith("Odoo")
            ):
                chosen[norm] = r
        return [Company(norm, r.name) for norm, r in chosen.items()]

    def save_many(self, results: list[NitResult]) -> list[str]:
        positives = self._dedupe_by_normalized_nit(results)
        if not positives:
            return []
        try:
            rows = self._company_repo.save_batch(positives)
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Fallo guardando caché local de NITs: {e}")
            raise NitCacheSaveError(str(e)) from e
        if rows is None:
            raise NitCacheSaveError("save_batch no pudo persistir el lote")

        self._by_nit = self._by_name = None
        persisted = {str(row[1]) for row in rows if row}
        return [c.nit for c in positives if c.nit not in persisted]
