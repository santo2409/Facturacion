from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.text_normalizer import normalize_nit


class SearchNitsWithOdooFallbackUseCase:
    """Resuelve NITs consultando primero Odoo/Avancys; solo scrapea RUES para
    los NITs que Odoo no tenga, de forma que el resultado final quede
    completamente documentado combinando ambas fuentes."""

    def __init__(
        self,
        search_nits_use_case: SearchNitsUseCase,
        odoo_repo=None,
        nit_cache_repo=None,
        logger=None,
    ):
        self.search_nits_use_case = search_nits_use_case
        self.odoo_repo = odoo_repo
        self.nit_cache_repo = nit_cache_repo
        self.logger = logger or LoggerAdapter(__name__)

    def _connect_odoo(self) -> None:
        if not self.odoo_repo:
            return
        try:
            self.odoo_repo.connect()
        except Exception as e:
            self.logger.warning(
                f"No se pudo conectar a Odoo: {e}",
                user_msg="No se pudo conectar a Odoo; se consultará RUES para todos los NITs.",
            )
            self.odoo_repo = None

    def execute(
        self,
        nits: list,
        show_progress: bool = False,
        book_names: dict[str, str] | None = None,
    ) -> list[NitResult]:
        book_names = book_names or {}
        resolved: dict[str, NitResult] = {}
        cached: dict[str, NitResult] = {}
        pending = list(nits)

        if self.nit_cache_repo:
            try:
                cached = self.nit_cache_repo.get_many([str(n) for n in nits])
            except Exception as e:
                self.logger.warning(f"Fallo consultando caché local de NITs: {e}")
                cached = {}
            resolved.update(cached)
            pending = [n for n in nits if str(n) not in cached]

        default_bases = "RUES"
        if pending:
            if not self.odoo_repo:
                for result in self._tag_bases(
                    self.search_nits_use_case.execute(pending, show_progress), "RUES"
                ):
                    resolved[str(result.nit)] = result
            else:
                self._connect_odoo()
                if not self.odoo_repo:
                    for result in self._tag_bases(
                        self.search_nits_use_case.execute(pending, show_progress), "RUES"
                    ):
                        resolved[str(result.nit)] = result
                else:
                    default_bases = "Odoo, RUES"
                    normalized_by_nit = {str(nit): normalize_nit(str(nit)) for nit in pending}
                    try:
                        batch_results = self.odoo_repo.find_clients_batch(
                            list(dict.fromkeys(normalized_by_nit.values()))
                        )
                    except Exception as e:
                        self.logger.warning(f"Fallo consultando Odoo en batch: {e}")
                        batch_results = {}

                    still_pending = []
                    for nit in pending:
                        match = batch_results.get(normalized_by_nit[str(nit)])
                        if match:
                            _, name, _ = match
                            resolved[str(nit)] = NitResult(
                                nit=nit, is_company=True, name=name, checked_bases="Odoo"
                            )
                        else:
                            still_pending.append(nit)

                    if still_pending:
                        for result in self._tag_bases(
                            self.search_nits_use_case.execute(still_pending, show_progress),
                            "Odoo, RUES",
                        ):
                            resolved[str(result.nit)] = result

        results = []
        for nit in nits:
            result = resolved.get(str(nit))
            if result is None:
                result = NitResult(nit=nit, is_company=False, checked_bases=default_bases)
            if not result.is_company and not result.name:
                result.name = book_names.get(str(nit))
            # Normaliza el tipo de `nit` a str: cada resultado puede venir de una
            # fuente distinta (caché en BD, Odoo, RUES) y cada una preserva un
            # tipo distinto para `nit`; sin esto, listas mixtas de str/int rompen
            # la construcción de DataFrames de Polars en los consumidores.
            result.nit = str(nit)
            results.append(result)

        if self.nit_cache_repo:
            new_positives = [r for r in results if r.is_company and str(r.nit) not in cached]
            if new_positives:
                try:
                    self.nit_cache_repo.save_many(new_positives)
                except Exception as e:
                    self.logger.warning(f"Fallo guardando caché local de NITs: {e}")

        return results

    @staticmethod
    def _tag_bases(results: list[NitResult], bases: str) -> list[NitResult]:
        for result in results:
            result.checked_bases = bases
        return results
