from src.scrapping.application.use_cases.search_nits_use_case import SearchNitsUseCase
from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.text_normalizer import normalize_company_name, normalize_nit

CONFLICT_DUPLICATE_NAME = "Nombre ya registrado en BD local con otro NIT"
DEFAULT_RUES_NAME_LIMIT = 200
ODOO_UNAVAILABLE_MSG = "Odoo no disponible: se validó con la BD local y RUES."

# Libro `bd_local_actualizada`: empresas que se agregaron o corrigieron en la BD
# local con los datos de Odoo (spec 016). Lo comparten las opciones 1, 2 y 5.
LOCAL_UPDATE_BOOK = "bd_local_actualizada"
LOCAL_UPDATE_COLUMNS = {
    LOCAL_UPDATE_BOOK: ["NIT", "Nombre en BD local", "Nombre en Odoo", "Acción"]
}
ACTION_ADDED = "Agregada"
ACTION_UPDATED = "Actualizada"
ACTION_NOT_UPDATED = "No actualizada: nombre duplicado en BD local"


class SearchNitsWithOdooFallbackUseCase:
    """Resuelve NITs en cascada con Odoo como fuente de verdad: Odoo (NIT y
    nombre), BD local como respaldo (NIT y nombre) y RUES (NIT y nombre). Cada
    paso recibe solo lo que los anteriores no resolvieron, y toda coincidencia
    por nombre se valida contra un umbral difuso antes de aceptarse."""

    def __init__(
        self,
        search_nits_use_case: SearchNitsUseCase,
        odoo_repo=None,
        nit_cache_repo=None,
        logger=None,
        name_matcher=None,
        local_name_lookup: bool = True,
        rues_name_limit: int = DEFAULT_RUES_NAME_LIMIT,
    ):
        self.search_nits_use_case = search_nits_use_case
        self.odoo_repo = odoo_repo
        self.nit_cache_repo = nit_cache_repo
        self.logger = logger or LoggerAdapter(__name__)
        self.name_matcher = name_matcher
        self.local_name_lookup = local_name_lookup
        self.rues_name_limit = rues_name_limit
        self.odoo_available = False
        self.local_updates: list[dict] = []

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

    def _safe(self, call, default, description: str):
        try:
            return call()
        except Exception as e:
            self.logger.warning(f"Fallo {description}: {e}")
            return default

    def _names_differ(self, book_name, found_name) -> bool:
        """True si el nombre del libro y el hallado difieren de verdad.

        Con `name_matcher` disponible, usa el mismo umbral difuso que ya
        decide si aceptar un candidato por nombre — evita marcar como novedad
        variantes de sufijo societario o espaciado ("SAS" vs "S A S"). Sin
        matcher, conserva la comparación exacta previa.
        """
        if not book_name:
            return False
        if self.name_matcher:
            return (
                self.name_matcher.best_match(book_name, [{"name": found_name or ""}])
                is None
            )
        return normalize_company_name(book_name) != normalize_company_name(found_name or "")

    def _resolve(
        self, key: str, book_name, found_name, found_nit, bases: str, source: str
    ) -> NitResult:
        """Construye el resultado y detecta las novedades frente al libro."""
        corrected = bool(found_nit) and normalize_nit(str(found_nit)) != normalize_nit(key)
        name_changed = self._names_differ(book_name, found_name)

        if corrected or name_changed:
            self.logger.info(
                f"[NOVEDAD] {key}: NIT '{key}' -> '{found_nit if corrected else key}', "
                f"nombre '{book_name}' -> '{found_name}' [{source}]",
                user_msg=(
                    f"Se corrigieron datos de la empresa '{found_name}'; "
                    "revisa empresas_no_encontradas.xlsx."
                ),
            )

        return NitResult(
            nit=str(found_nit) if corrected else key,
            is_company=True,
            name=found_name,
            checked_bases=bases,
            source=source,
            nit_original=key if corrected else None,
            name_original=book_name if name_changed else None,
        )

    def execute(
        self,
        nits: list,
        show_progress: bool = False,
        book_names: dict[str, str] | None = None,
    ) -> list[NitResult]:
        book_names = book_names or {}
        originals = {str(n): n for n in nits}
        keys = list(originals)
        resolved: dict[str, NitResult] = {}
        known_nits: set[str] = set()

        def pending() -> list[str]:
            return [k for k in keys if k not in resolved]

        def pending_names() -> dict[str, list[str]]:
            """{nombre del libro: claves pendientes con ese nombre}."""
            groups: dict[str, list[str]] = {}
            for key in pending():
                name = (book_names.get(key) or "").strip()
                if name:
                    groups.setdefault(name, []).append(key)
            return groups

        # ── 1. BD local por NIT ──────────────────────────────────────────
        if self.nit_cache_repo:
            cached = self._safe(
                lambda: self.nit_cache_repo.get_many(keys), {}, "consultando caché local de NITs"
            )
            for key, hit in cached.items():
                known_nits.add(normalize_nit(str(hit.nit)))
                resolved[key] = self._resolve(
                    key, book_names.get(key), hit.name, None, "BD local", "BD local/NIT"
                )

            # ── 2. BD local por nombre ───────────────────────────────────
            if self.local_name_lookup:
                groups = pending_names()
                if groups:
                    by_name = self._safe(
                        lambda: self.nit_cache_repo.get_by_names(list(groups)),
                        {},
                        "consultando caché local por nombre",
                    )
                    for name, hit in by_name.items():
                        known_nits.add(normalize_nit(str(hit.nit)))
                        for key in groups.get(name, []):
                            resolved[key] = self._resolve(
                                key, name, hit.name, str(hit.nit), "BD local", "BD local/nombre"
                            )

        self._connect_odoo()
        default_bases = "Odoo, RUES" if self.odoo_repo else "RUES"

        # ── 3. Odoo por NIT (una sola llamada) ───────────────────────────
        if self.odoo_repo and pending():
            normalized = {key: normalize_nit(key) for key in pending()}
            batch = self._safe(
                lambda: self.odoo_repo.find_clients_batch(
                    list(dict.fromkeys(normalized.values()))
                ),
                {},
                "consultando Odoo en batch",
            )
            for key, norm in normalized.items():
                match = batch.get(norm)
                if match:
                    _, name, _ = match
                    resolved[key] = self._resolve(
                        key, book_names.get(key), name, None, "Odoo", "Odoo/NIT"
                    )

        # ── 4. Odoo por nombre ───────────────────────────────────────────
        if self.odoo_repo and self.name_matcher and pending():
            for name, group in pending_names().items():
                candidates = self._safe(
                    lambda n=name: self.odoo_repo.find_clients_by_name(n),
                    [],
                    f"buscando '{name}' por nombre en Odoo",
                )
                winner = self.name_matcher.best_match(name, candidates)
                if not winner or not winner.get("vat"):
                    continue
                for key in group:
                    resolved[key] = self._resolve(
                        key, name, winner["name"], winner["vat"], "Odoo", "Odoo/nombre"
                    )

        # ── 5. RUES por NIT ──────────────────────────────────────────────
        if pending():
            scraped = self._safe(
                lambda: self.search_nits_use_case.execute(
                    [originals[k] for k in pending()], show_progress
                ),
                [],
                "consultando RUES por NIT",
            )
            by_norm = {
                normalize_nit(str(r.nit)): r for r in scraped if r and r.is_company
            }
            for key in pending():
                hit = by_norm.get(normalize_nit(key))
                if hit:
                    resolved[key] = self._resolve(
                        key, book_names.get(key), hit.name, None, default_bases, "RUES/NIT"
                    )

        # ── 6. RUES por nombre ───────────────────────────────────────────
        if self.name_matcher and pending():
            groups = pending_names()
            names = list(groups)
            if len(names) > self.rues_name_limit:
                self.logger.warning(
                    f"{len(names)} nombres pendientes en RUES; se consultarán "
                    f"{self.rues_name_limit}",
                    user_msg=(
                        f"{len(names) - self.rues_name_limit} empresa(s) quedaron sin "
                        "consulta por nombre en RUES por el límite configurado "
                        "(RUES_NAME_LOOKUP_LIMIT)."
                    ),
                )
                names = names[: self.rues_name_limit]

            if names:
                found = self._safe(
                    lambda: self.search_nits_use_case.execute_names(names, show_progress),
                    {},
                    "consultando RUES por nombre",
                )
                for name, hit in found.items():
                    if not hit or not hit.is_company:
                        continue
                    if not self.name_matcher.best_match(name, [{"name": hit.name}]):
                        continue
                    for key in groups.get(name, []):
                        resolved[key] = self._resolve(
                            key, name, hit.name, str(hit.nit), default_bases, "RUES/nombre"
                        )

        # ── 7. Ensamblado: un resultado por NIT de entrada, en orden ──────
        results: list[NitResult] = []
        for key in keys:
            result = resolved.get(key)
            if result is None:
                result = NitResult(
                    nit=key,
                    is_company=False,
                    name=book_names.get(key),
                    checked_bases=default_bases,
                )
            results.append(result)

        # ── Persistencia en BD local y reporte de conflictos ─────────────
        if self.nit_cache_repo:
            nuevos = [
                r for r in results
                if r.is_company and normalize_nit(str(r.nit)) not in known_nits
            ]
            if nuevos:
                omitted = self._safe(
                    lambda: self.nit_cache_repo.save_many(nuevos),
                    [],
                    "guardando caché local de NITs",
                ) or []
                omitted_nits = {normalize_nit(str(o)) for o in omitted}
                for result in nuevos:
                    if normalize_nit(str(result.nit)) in omitted_nits:
                        result.conflict = CONFLICT_DUPLICATE_NAME

        return results
