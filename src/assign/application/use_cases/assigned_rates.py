import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from src.assign.domain.odoo_rate_index import OdooRateIndex
from src.company.domain.entities.imedical_correction import ImedicalCorrection
from src.company.domain.entities.tian_assignment import TianAssignment
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.scrapping.domain.entities.nit_result import NitResult
from src.shared.config import get_paths_config, get_tian_config
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.utils.company_name_matcher import CompanyNameMatcher
from src.shared.utils.text_normalizer import (
    normalize_name,
    pl_normalize_name,
    pl_normalize_upper,
)
from src.special.domain.entities.special import Special


def _fecha_warning(fecha, fecha_limite) -> str:
    """Retorna advertencia si la fecha es > 3 meses antes del límite."""
    from datetime import timedelta
    tres_meses_antes = fecha_limite - timedelta(days=90)
    if fecha < tres_meses_antes:
        return f"fuera del periodo habitual (> 3 meses: {fecha})"
    if fecha > fecha_limite:
        return f"fecha futura respecto al periodo ({fecha} > {fecha_limite})"
    return ""


def _es_base_imedical(base) -> bool:
    """True si la columna Base de la fila proviene de i-medical (spec 008
    RF-06a). Tolerante a mayúsculas/minúsculas y a variantes con guiones o
    espacios (ej. 'IMEDICAL AGOSTO 1-20', 'imedical agosto 1-20')."""
    if not base:
        return False
    return "IMEDICAL" in normalize_name(str(base))


def _enrich_with_invoices(df: pl.DataFrame, df_facture: pl.DataFrame, logger) -> pl.DataFrame:
    """Añade columna FACTURAS a df cruzando por N° Identificación."""
    id_col = "N° Identificación"
    fac_col = "# FACTURA"

    df = df.with_columns(
        pl.col(id_col).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias(id_col)
    )

    df_facture = (
        df_facture
        .with_columns(
            pl.col(id_col).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias(id_col)
        )
        .unique(subset=[id_col, fac_col])
    )

    duplicados = df_facture.group_by(id_col).len().filter(pl.col("len") > 1).height
    if duplicados:
        logger.warning(f"{duplicados} identificaciones con más de una factura. Se concatenarán.")

    df_grp = df_facture.group_by(id_col).agg(
        pl.col(fac_col).str.join(", ").alias("FACTURAS")
    )

    df = df.join(df_grp, on=id_col, how="left").with_columns(
        pl.col("FACTURAS").fill_null("")
    )

    sin_factura = df.filter(pl.col("FACTURAS") == "").height
    logger.info(
        f"Enriquecimiento facturas: {df.height - sin_factura} con match, {sin_factura} sin factura.",
    )
    return df


PHASE_FINDING_KEYS = (
    "fase_01_paquete_propio_local",
    "fase_02_paquete_c_2025",
    "fase_03_cualquier_paquete",
    "fase_04_cup_base_paquete_c",
    "fase_05_cup_base_cualquier_paquete",
    "fase_06_cualquier_ciudad",
    "sin_resolver",
)
_COLOR_LOCAL_OWN = "E2EFDA"  # Verde claro — fase 1 local (paquete propio)

_PHASE_LEGEND = [
    (_COLOR_LOCAL_OWN, "Fase 1 — Paquete propio local"),
    ("FFF2CC", "Fase 2 — PAQUETE C 2025 (mismo CUP, misma ciudad)"),
    ("F4B183", "Fase 3 — Cualquier paquete (mismo CUP, misma ciudad)"),
    ("BDD7EE", "Fase 4 — PAQUETE C 2025 (CUP base, misma ciudad)"),
    ("9DC3E6", "Fase 5 — Cualquier paquete (CUP base, misma ciudad)"),
    ("D5A6E6", "Fase 6 — Cualquier paquete/ciudad (cup + actividad)"),
]


@dataclass
class AssignRatesResult:
    counts: dict[str, int] = field(default_factory=dict)
    findings_dir: Path | None = None
    odoo_available: bool = False


class AssignRatesFromExcel:
    def __init__(
        self,
        biller_repo,
        company_repo,
        biller_company_repo,
        package_repo,
        provider_repo,
        special_repo,
        city_repo,
        activities_repo,
        rates_repo,
        cup_repo,
        fuzz,
        progress,
        logger,
        odoo_repo=None,
        not_found_log_generator=None,
        logs_dir: Path = Path("logs"),
        imedical_repo=None,
        tian_repo=None,
        tian_log_generator=None,
        findings_reporter=None,
    ):
        self.biller_repo = biller_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.package_repo = package_repo
        self.provider_repo = provider_repo
        self.special_repo = special_repo
        self.city_repo = city_repo
        self.activities_repo = activities_repo
        self.rates_repo = rates_repo
        self.cup_repo = cup_repo
        self.fuzz = fuzz
        self.progress = progress
        self.logger = logger or LoggerAdapter(__name__)
        self.odoo_repo = odoo_repo
        self.not_found_log_generator = not_found_log_generator
        self.logs_dir = logs_dir
        self.imedical_repo = imedical_repo
        self.tian_repo = tian_repo
        self.tian_log_generator = tian_log_generator
        self.findings_reporter = findings_reporter
        self.odoo_available = False
        self._odoo_by_nit: dict[str, dict] = {}
        self._odoo_index = OdooRateIndex([])
        self._company_findings: list[dict] = []
        self._findings: dict[str, list[dict]] = {key: [] for key in PHASE_FINDING_KEYS}
        self._odoo_cells = 0

    def _connect_odoo(self) -> None:
        if not self.odoo_repo:
            return
        try:
            self.odoo_repo.connect()
        except Exception as e:
            self.logger.warning(
                f"No se pudo conectar a Odoo: {e}",
            )
            self.odoo_repo = None

    def _load_odoo_rates(self, df: pl.DataFrame) -> None:
        """Consulta en batch las tarifas (especial/base) de las empresas en Odoo.

        Si Odoo no está disponible o falla la consulta, queda sin tarifas y la
        cascada local resuelve todo (spec 010, RF-14).
        """
        self.odoo_available = False
        self._odoo_by_nit = {}
        self._odoo_index = OdooRateIndex([])
        self._company_findings = []
        if not self.odoo_repo:
            return

        nits = list(dict.fromkeys(n for n in df["NIT"].to_list() if n))
        cups = [str(h) for h in df.columns if str(h).replace("-", "").isdigit()]
        try:
            partners = self.odoo_repo.find_partner_rates_batch(nits)
            rate_ids = list(dict.fromkeys(
                i for p in partners for i in (p["special_id"], p["base_id"]) if i
            ))
            lines = self.odoo_repo.find_rate_lines(rate_ids, cups) if rate_ids and cups else []
        except Exception as e:
            self.logger.warning(
                f"No se pudieron consultar las tarifas en Odoo; se usará la cascada local: {e}"
            )
            return

        self._odoo_by_nit = {p["nit"]: p for p in partners}
        self._odoo_index = OdooRateIndex(lines)
        self.odoo_available = True

        names: dict[str, str] = {}
        if "Empresa" in df.columns:
            for nit, name in zip(df["NIT"].to_list(), df["Empresa"].to_list()):
                names.setdefault(nit, name)
        for nit in nits:
            partner = self._odoo_by_nit.get(nit)
            if partner is None:
                reason = "No encontrada en Odoo"
            elif not partner["special_id"] and not partner["base_id"]:
                reason = "Sin tarifa especial ni base"
            else:
                continue
            self._company_findings.append(
                {"NIT": nit, "Empresa": names.get(nit) or "", "Motivo": reason}
            )

    def execute(self, excel: pl.DataFrame, df_facture: pl.DataFrame):
        self._connect_odoo()

        lookups = self._build_lookups()
        df = self._capture_raw_nit(excel)
        df = self._apply_imedical(df, lookups)
        df = self._normalize_nit(df)
        df = self._match_companies(df, lookups)
        # _match_companies puede reemplazar el NIT con valores provenientes de
        # Odoo (get_nit) o de RUES (data.json), que no pasan por el mismo
        # truncamiento a 9 dígitos aplicado al NIT original del Excel.
        df = self._normalize_nit(df)
        df = self._normalize_columns(df)
        # _apply_tian va después de _normalize_columns: pl_normalize_name
        # borra los paréntesis, así que el sufijo "(TIAN)" solo puede
        # aplicarse una vez la razón social ya quedó normalizada. Va antes
        # de asignar facturador/paquete/tarifas (RF-13) para que la fila
        # herede los de TIAN.
        df = self._apply_tian(df, lookups)
        df = self._normalize_city(df, lookups)
        self._load_odoo_rates(df)
        df = self._assign_facturador(df, lookups)
        df = self._assign_paquete(df, lookups)
        df, cell_colors = self._assign_rates(df, lookups)
        df = self._validate_empresa(df, lookups)
        df = self._drop_internal_columns(df)
        df = _enrich_with_invoices(df, df_facture, self.logger)
        df = self._order_columns(df)

        with self.progress("Exportando consolidado", total=1):
            import xlsxwriter as _xlsxwriter
            workbook = _xlsxwriter.Workbook("CONSOLIDADO.xlsx")
            df.write_excel(
                workbook,
                worksheet="Consolidado",
                table_style="Table Style Medium 2",
            )
            # Apply cell colors from cascade fallback phases
            if cell_colors:
                ws = workbook.get_worksheet_by_name("Consolidado")
                if ws is not None:
                    # Build column index map: col_name → xlsxwriter col index
                    col_names = df.columns
                    col_index = {name: i for i, name in enumerate(col_names)}
                    # Row 0 = header, data starts at row 1
                    fmt_cache = {}
                    for (col_name, row_idx), color in cell_colors.items():
                        if col_name not in col_index:
                            continue
                        if color not in fmt_cache:
                            fmt_cache[color] = workbook.add_format({
                                "bg_color": f"#{color}",
                                "num_format": "#,##0",
                            })
                        ws.write(row_idx + 1, col_index[col_name],
                                 df[col_name][row_idx], fmt_cache[color])

            if cell_colors or self._odoo_cells:
                self._write_legend(workbook)
            workbook.close()
            self.progress.advance()

        return self._publish_findings()

    # ── Column ordering ───────────────────────────────────────────────────

    _FIXED_COLUMNS_ORDER = [
        "Base",
        "Ingreso N°",
        "Sede",
        "Ciudad",
        "NIT",
        "FACTURADOR",
        "Especial / General",
        "PAQUETE",
        "Empresa",
        "Empresa Misión",
        "Medio de Pago",
        "Fecha Ingreso",
        "Tipo Examen",
        "Cargo",
        "Paciente",
        "N° Identificación",
        "Número de Póliza",
        "ORDEN, CENTRO DE COSTO, CECO, PET",
        "ORDEN, CENTRO DE COSTO, CECO, PET_1",
        "FACTURAS",
        "TIPO DE ACTIVIDAD",
        "Observaciones Ingreso",
        "Total",
    ]

    # Columnas auxiliares usadas internamente por el pipeline (spec 008
    # RF-23): nunca deben llegar al CONSOLIDADO.xlsx.
    _INTERNAL_COLUMNS = ("_NIT_RAW", "_PAQUETE_LOCAL")

    def _write_legend(self, workbook) -> None:
        legend_ws = workbook.add_worksheet("Leyenda")
        legend_ws.set_column(0, 0, 6)
        legend_ws.set_column(1, 1, 55)
        legend_ws.write(0, 0, "Color", workbook.add_format({"bold": True}))
        legend_ws.write(0, 1, "Significado", workbook.add_format({"bold": True}))
        white_fmt = workbook.add_format({"bg_color": "#FFFFFF"})
        legend_ws.write(1, 0, "", white_fmt)
        legend_ws.write(1, 1, "Sin color — Tarifa Odoo (especial/base)")
        for row, (color, label) in enumerate(_PHASE_LEGEND, start=2):
            fmt = workbook.add_format({"bg_color": f"#{color}"})
            legend_ws.write(row, 0, "", fmt)
            legend_ws.write(row, 1, label)

    def _publish_findings(self) -> AssignRatesResult:
        findings_dir = None
        if self.findings_reporter:
            findings_dir = self.findings_reporter.write(self._findings, self._company_findings)
        counts = {"odoo": self._odoo_cells}
        counts.update({key: len(rows) for key, rows in self._findings.items()})
        return AssignRatesResult(
            counts=counts, findings_dir=findings_dir, odoo_available=self.odoo_available
        )

    def _drop_internal_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        presentes = [c for c in self._INTERNAL_COLUMNS if c in df.columns]
        return df.drop(presentes) if presentes else df

    def _order_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        fixed = [c for c in self._FIXED_COLUMNS_ORDER if c in df.columns]
        others = sorted(
            [c for c in df.columns if c not in set(self._FIXED_COLUMNS_ORDER)],
            key=lambda x: (int(x.split("-")[0]) if x.replace("-", "").isdigit() else float("inf"), x),
        )
        return df.select(fixed + others)

    # ── Build lookup dictionaries O(1) ────────────────────────────────────

    def _build_lookups(self) -> dict:
        companies_all = self.company_repo.all()
        biller_companies_all = self.biller_company_repo.all()
        billers_all = self.biller_repo.all()
        companies_rates_all = self.company_repo.companies_packages_all()
        packages_all = self.package_repo.all()
        providers_all = self.provider_repo.all()
        special_all = self.special_repo.all()
        cities_all = self.city_repo.all()
        activity_all = self.activities_repo.all()
        cup_all = self.cup_repo.get_all()

        # NIT → company dict
        nit_to_company = {c["nit"]: c for c in companies_all}
        # name (normalized) → company dict
        name_to_company = {normalize_name(c["name"]): c for c in companies_all}
        # company_id → (package_id, model)
        company_to_package = {c["company"]: (c["package"], c["model"]) for c in companies_rates_all}
        # company_id → biller_id
        company_to_biller = {bc["company"]: bc["biller"] for bc in biller_companies_all}
        # biller_id → name
        biller_id_to_name = {b["id"]: b["name"] for b in billers_all}
        # city name → id
        city_name_to_id = {c["name"]: c["id"] for c in cities_all}
        # cup code → id
        cup_code_to_id = {c["code"].strip(): c["id"] for c in cup_all}
        # activity name → id
        activity_name_to_id = {c["name"]: c["id"] for c in activity_all}
        # package name → (id, model)
        package_name_to_id = {c["name"]: (c["id"], Package.__name__) for c in packages_all}

        # Scraped NITs from JSON
        scraped_nits = {}
        scraped_name_to_nit = {}
        json_path = os.path.join(get_paths_config()["directory"], "data.json")
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                for item in json.load(f):
                    nit = str(item.get("nit", ""))
                    name = item.get("name", "")
                    if nit:
                        scraped_nits[nit] = name
                    if name:
                        scraped_name_to_nit[normalize_name(name)] = nit

        # imedical: nit_error (crudo) -> nit_success, solo correcciones reales
        # (spec 008 RF-03): se excluyen las filas no-op (nit_error == nit_success)
        # y aquellas que el truncado a 9 dígitos ya resuelve sin tabla alguna.
        # Se indexa por clave doble (cruda y truncada a 9) para que la corrección
        # se aplique aunque el DataFrame no traiga la columna _NIT_RAW (RF-02).
        imedical_map: dict[str, str] = {}
        imedical_known_nit_errors: set[str] = set()
        if self.imedical_repo:
            for row in self.imedical_repo.all():
                raw = re.sub(r"\D", "", str(row["nit_error"]))
                success = str(row["nit_success"])
                imedical_known_nit_errors.add(raw)
                if not raw or raw == success:
                    continue
                if raw[:9] == success:
                    continue
                imedical_map[raw] = success
                truncated = raw[:9]
                if truncated != raw:
                    imedical_map[truncated] = success

        # tian: NITs que deben facturarse bajo TIAN_NIT (spec 008 RF-12/RF-16).
        # Se excluye el propio NIT de TIAN para que no se auto-redirija.
        tian_nit = get_tian_config()["nit"]
        tian_nits: set[str] = set()
        if self.tian_repo:
            for row in self.tian_repo.all():
                raw = re.sub(r"\D", "", str(row["nit_error"]))
                if raw and raw != tian_nit:
                    tian_nits.add(raw)

        return {
            "nit_to_company": nit_to_company,
            "name_to_company": name_to_company,
            "company_to_package": company_to_package,
            "company_to_biller": company_to_biller,
            "biller_id_to_name": biller_id_to_name,
            "city_name_to_id": city_name_to_id,
            "cup_code_to_id": cup_code_to_id,
            "activity_name_to_id": activity_name_to_id,
            "package_name_to_id": package_name_to_id,
            "scraped_nits": scraped_nits,
            "scraped_name_to_nit": scraped_name_to_nit,
            "cities_all": cities_all,
            "packages_all": packages_all,
            "imedical_map": imedical_map,
            "imedical_known_nit_errors": imedical_known_nit_errors,
            "tian_nits": tian_nits,
            "tian_nit": tian_nit,
        }

    # ── i-medical: NIT crudo y corrección (spec 008 RF-01..05) ─────────────

    def _capture_raw_nit(self, df: pl.DataFrame) -> pl.DataFrame:
        """Guarda el NIT en dígitos crudos, SIN truncar (RF-02): _normalize_nit
        trunca a 9 dígitos y el lookup de imedical necesita el valor completo,
        porque 64 de las 103 filas de la tabla tienen nit_error de 10+ dígitos."""
        return df.with_columns(
            pl.col("NIT")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace_all(r"[^\d]", "")
            .alias("_NIT_RAW")
        )

    def _apply_imedical(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        """Corrige el NIT usando la tabla imedical (nit_error -> nit_success).

        Usa _NIT_RAW si está presente (flujo normal de execute()); si no,
        tolera ser invocado con un DataFrame mínimo limpiando NIT en el acto
        (para tests que ejercitan el método aislado)."""
        imedical_map = lookups.get("imedical_map", {})
        if not imedical_map:
            return df

        raw_source = "_NIT_RAW" if "_NIT_RAW" in df.columns else "NIT"
        raw_nits = (
            df[raw_source]
            .cast(pl.Utf8)
            .str.replace_all(r"[^\d]", "")
            .to_list()
        )

        locked_nits = lookups.setdefault("imedical_locked_nits", set())
        corregidos = []
        nuevos_nit = list(df["NIT"].cast(pl.Utf8))
        for i, raw in enumerate(raw_nits):
            nit_success = imedical_map.get(raw)
            if nit_success and nit_success != nuevos_nit[i]:
                corregidos.append((raw, nit_success))
                nuevos_nit[i] = nit_success
                locked_nits.add(nit_success)

        if corregidos:
            unique = sorted(set(corregidos))
            self.logger.info(
                f"imedical: {len(corregidos)} NIT corregido(s):\n"
                + "\n".join(f"  {origen} → {destino}" for origen, destino in unique),
            )

        return df.with_columns(pl.Series("NIT", nuevos_nit))

    # ── NIT normalization ─────────────────────────────────────────────────

    def _normalize_nit(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(
            pl.col("NIT")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace_all(r"[^\d]", "")
            .str.slice(0, 9)
            .alias("NIT")
        )

    # ── Match companies by NIT ────────────────────────────────────────────

    def _match_companies(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        name_to_company = lookups["name_to_company"]
        odoo_resolved_nits = lookups.setdefault("odoo_resolved_nits", set())
        imedical_locked_nits = lookups.get("imedical_locked_nits", set())
        _odoo_nit_cache: dict = {}
        _odoo_name_cache: dict = {}

        # ── Auto-registro en imedical (spec 008 RF-06..RF-11) ───────────────
        imedical_known_nit_errors = lookups.get("imedical_known_nit_errors", set())
        tiene_columna_base = "Base" in df.columns
        if self.imedical_repo and not tiene_columna_base:
            self.logger.warning(
                "imedical: el libro de entrada no tiene columna 'Base'; se omite el auto-registro.",
            )
        candidatos_imedical: dict[str, ImedicalCorrection] = {}
        name_matcher = CompanyNameMatcher(self.fuzz, threshold=90) if self.imedical_repo else None

        matched_nits = []
        matched_empresas = []
        cambios = []
        not_found_by_nit: dict[str, NitResult] = {}

        with self.progress("Validando empresas", total=df.height):
            for row in df.iter_rows(named=True):
                nit = row["NIT"]
                empresa = row["Empresa"]

                # ── 1. Odoo por NIT ───────────────────────────────────────────
                if nit and self.odoo_repo:
                    if nit not in _odoo_nit_cache:
                        try:
                            cid, cname, _ = self.odoo_repo.find_client(nit, empresa)
                            _odoo_nit_cache[nit] = (cid, cname)
                        except Exception as e:
                            self.logger.warning(f"Fallo consultando Odoo por NIT {nit}: {e}")
                            _odoo_nit_cache[nit] = (None, None)

                    odoo_id, odoo_name = _odoo_nit_cache.get(nit, (None, None))
                    if odoo_id and odoo_name:
                        if odoo_name != empresa:
                            cambios.append(f"NIT {nit}: nombre '{empresa}' → '{odoo_name}' [Odoo/NIT]")
                        matched_nits.append(nit)
                        matched_empresas.append(odoo_name)
                        odoo_resolved_nits.add(nit)
                        self.progress.advance()
                        continue

                # ── 1.5. Odoo por nombre ──────────────────────────────────────
                if empresa and self.odoo_repo:
                    if empresa not in _odoo_name_cache:
                        try:
                            cid, cname, _ = self.odoo_repo.find_client_by_name(empresa)
                            nuevo_nit = self.odoo_repo.get_nit(cid) if cid else None
                            _odoo_name_cache[empresa] = (cid, cname, nuevo_nit)
                        except Exception as e:
                            self.logger.warning(f"Fallo consultando Odoo por nombre '{empresa}': {e}")
                            _odoo_name_cache[empresa] = (None, None, None)

                    odoo_id, odoo_name_match, odoo_nit = _odoo_name_cache.get(empresa, (None, None, None))
                    if odoo_id and odoo_nit:
                        if nit in imedical_locked_nits and odoo_nit != nit:
                            cambios.append(
                                f"[NOVEDAD] imedical bloqueó cambio de NIT {nit} → {odoo_nit} "
                                f"sugerido por Odoo/nombre"
                            )
                            matched_nits.append(nit)
                            matched_empresas.append(empresa)
                            self.progress.advance()
                            continue
                        if odoo_nit != nit:
                            cambios.append(f"Empresa '{empresa}': NIT '{nit}' → '{odoo_nit}' [Odoo/nombre]")

                        # ── R2: auto-registro en imedical (RF-06..RF-11) ──
                        raw_nit_error = row.get("_NIT_RAW") or nit
                        if (
                            self.imedical_repo
                            and tiene_columna_base
                            and _es_base_imedical(row.get("Base"))
                            and raw_nit_error
                            and raw_nit_error != odoo_nit
                            and raw_nit_error[:9] != odoo_nit
                            and raw_nit_error not in imedical_known_nit_errors
                            and raw_nit_error not in candidatos_imedical
                            and odoo_name_match
                        ):
                            match = name_matcher.best_match(empresa, [{"name": odoo_name_match}])
                            if match:
                                candidatos_imedical[raw_nit_error] = ImedicalCorrection(
                                    nit_error=raw_nit_error,
                                    nit_success=odoo_nit,
                                    name=odoo_name_match,
                                    name_error=empresa,
                                )

                        matched_nits.append(odoo_nit)
                        matched_empresas.append(empresa)
                        odoo_resolved_nits.add(odoo_nit)
                        self.progress.advance()
                        continue

                # ── 2. BD local por NIT ───────────────────────────────────────
                if nit and nit in nit_to_company:
                    nuevo_nombre = nit_to_company[nit]["name"]
                    if nuevo_nombre != empresa:
                        cambios.append(f"NIT {nit}: nombre '{empresa}' → '{nuevo_nombre}' [BD local]")
                    matched_nits.append(nit)
                    matched_empresas.append(nuevo_nombre)
                    self.progress.advance()
                    continue

                # ── 2.5. BD local por nombre (NIT erróneo en Excel) ───────────
                empresa_norm = normalize_name(empresa) if empresa else ""
                if empresa_norm and empresa_norm in name_to_company:
                    comp = name_to_company[empresa_norm]
                    if nit in imedical_locked_nits and comp["nit"] != nit:
                        cambios.append(
                            f"[NOVEDAD] imedical bloqueó cambio de NIT {nit} → {comp['nit']} "
                            f"sugerido por BD local/nombre"
                        )
                        matched_nits.append(nit)
                        matched_empresas.append(comp["name"])
                        self.progress.advance()
                        continue
                    cambios.append(f"Empresa '{empresa}': NIT '{nit}' → '{comp['nit']}' [BD local/nombre]")
                    matched_nits.append(comp["nit"])
                    matched_empresas.append(comp["name"])
                    self.progress.advance()
                    continue

                # ── 3. RUES por NIT (data.json) ──────────────────────────────────
                scraped_nits = lookups["scraped_nits"]
                if nit and nit in scraped_nits:
                    scraped_name = scraped_nits[nit]
                    if scraped_name:
                        if scraped_name != empresa:
                            cambios.append(f"NIT {nit}: nombre '{empresa}' → '{scraped_name}' [RUES/NIT]")
                        matched_nits.append(nit)
                        matched_empresas.append(scraped_name)
                        self.progress.advance()
                        continue

                # ── 3.5. RUES por nombre (data.json) ──────────────────────────
                scraped_name_to_nit = lookups["scraped_name_to_nit"]
                empresa_norm = normalize_name(empresa) if empresa else ""
                if empresa_norm and empresa_norm in scraped_name_to_nit:
                    nuevo_nit = scraped_name_to_nit[empresa_norm]
                    if nit in imedical_locked_nits and nuevo_nit and nuevo_nit != nit:
                        cambios.append(
                            f"[NOVEDAD] imedical bloqueó cambio de NIT {nit} → {nuevo_nit} "
                            f"sugerido por RUES/nombre"
                        )
                        matched_nits.append(nit)
                        matched_empresas.append(empresa)
                        self.progress.advance()
                        continue
                    if nuevo_nit and nuevo_nit != nit:
                        cambios.append(f"Empresa '{empresa}': NIT '{nit}' → '{nuevo_nit}' [RUES/nombre]")
                    matched_nits.append(nuevo_nit or nit)
                    matched_empresas.append(empresa)
                    self.progress.advance()
                    continue

                # ── 4. Sin resultado — se deja el dato y se registra NOVEDAD ──
                novedad = f"[NOVEDAD] NIT {nit} - '{empresa}': no encontrado en Odoo, BD local ni RUES"
                cambios.append(novedad)
                self.logger.warning(novedad)
                not_found_by_nit[nit] = NitResult(
                    nit=nit,
                    is_company=False,
                    name=empresa,
                    checked_bases="Odoo, BD local, RUES" if self.odoo_repo else "BD local, RUES",
                )
                matched_nits.append(nit)
                matched_empresas.append(empresa)
                self.progress.advance()

        # Registrar todos los cambios/novedades
        if cambios:
            self.logger.info(
                f"_match_companies: {len(cambios)} cambios/novedades:\n" + "\n".join(f"  {c}" for c in cambios),
            )

        if not_found_by_nit and self.not_found_log_generator:
            self.not_found_log_generator.generate(list(not_found_by_nit.values()), self.logs_dir)

        # ── R4: nombre canónico por NIT (spec 008 RF-21/RF-22) ──────────────
        # Las ramas por NIT (1, 2, 3) ya resuelven el nombre desde una fuente
        # autoritativa aplicada de forma idéntica a cada fila de ese NIT, así
        # que por sí solas no producen divergencia. El hueco real está en las
        # ramas por nombre (1.5, 3.5), que conservan el nombre crudo del
        # Excel: si dos filas con NIT distinto en el Excel terminan en el
        # mismo NIT final por esas ramas, cada una conserva SU propio nombre
        # original y quedan divergentes para un mismo NIT.
        #
        # Se actúa solo cuando hay divergencia real dentro de este lote (no
        # se toca un NIT con un único nombre ya consistente), para no
        # adelantar aquí la corrección contra BD que _validate_empresa aplica
        # deliberadamente después. Nunca por similitud (AC-27): la clave es
        # siempre el NIT final, jamás el nombre.
        name_variants_by_nit: dict[str, set] = {}
        for resolved_nit, empresa_resuelta in zip(matched_nits, matched_empresas):
            if resolved_nit:
                name_variants_by_nit.setdefault(resolved_nit, set()).add(empresa_resuelta)
        nits_con_divergencia = {nit for nit, names in name_variants_by_nit.items() if len(names) > 1}

        if nits_con_divergencia:
            canonical_name_by_nit: dict[str, str] = {}
            for i, resolved_nit in enumerate(matched_nits):
                if (
                    resolved_nit in nits_con_divergencia
                    and resolved_nit in odoo_resolved_nits
                    and resolved_nit not in canonical_name_by_nit
                ):
                    canonical_name_by_nit[resolved_nit] = matched_empresas[i]
            for i, resolved_nit in enumerate(matched_nits):
                if (
                    resolved_nit in nits_con_divergencia
                    and resolved_nit in nit_to_company
                    and resolved_nit not in canonical_name_by_nit
                ):
                    canonical_name_by_nit[resolved_nit] = nit_to_company[resolved_nit]["name"]
            for i, resolved_nit in enumerate(matched_nits):
                if resolved_nit in nits_con_divergencia and resolved_nit not in canonical_name_by_nit:
                    canonical_name_by_nit[resolved_nit] = matched_empresas[i]
            for i, resolved_nit in enumerate(matched_nits):
                if resolved_nit in nits_con_divergencia:
                    matched_empresas[i] = canonical_name_by_nit[resolved_nit]

        if candidatos_imedical and self.imedical_repo:
            n = self.imedical_repo.save_batch(list(candidatos_imedical.values()))
            if n:
                self.logger.info(
                    f"imedical: {n} corrección(es) nueva(s) registrada(s) automáticamente:\n"
                    + "\n".join(
                        f"  {c.nit_error} → {c.nit_success} ('{c.name_error}' → '{c.name}')"
                        for c in candidatos_imedical.values()
                    ),
                )

        return df.with_columns([
            pl.Series("NIT", matched_nits),
            pl.Series("Empresa", matched_empresas),
        ])

    # ── Column normalization ──────────────────────────────────────────────

    def _normalize_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        # Normalizar Fecha Ingreso
        df = self._normalize_fecha(df)

        return df.with_columns([
            pl_normalize_name("Empresa")
            .str.replace_all(r"\bS\s+A\s+S\b", "SAS")
            .str.replace_all(r"\bS\s+A\b", "SA")
            .str.replace_all(r"\bL\s+T\s+D\s+A\b", "LTDA")
            .str.replace_all(r"\bE\s+U\b", "EU")
            .str.replace_all(r"\bE\s+S\s+P\b", "ESP")
            .alias("Empresa"),
            pl_normalize_name("Empresa Misión").alias("Empresa Misión"),
            pl_normalize_name("Sede").alias("Sede"),
            pl_normalize_upper("Medio de Pago").cast(pl.Utf8).alias("Medio de Pago"),
            pl_normalize_upper("Tipo Examen").cast(pl.Utf8).alias("Tipo Examen"),
            (
                pl.col("Cargo")
                .str.strip_chars()
                .str.to_uppercase()
                .str.replace_all(r"[^A-Z&Ñ#0-9\s]", "")
                .str.replace_all(r"\s+", " ")
                .cast(pl.Utf8)
                .alias("Cargo")
            ),
            pl_normalize_name("Paciente").cast(pl.Utf8).alias("Paciente"),
            (
                pl.col("TIPO DE ACTIVIDAD")
                .fill_null("INTRA")
                .str.strip_chars()
                .str.to_uppercase()
                .str.replace_all("INTRAMURAL", "INTRA")
                .str.replace_all("EXTRAMURAL", "EXTRA")
                .str.replace_all(r"[^A-Z&Ñ0-9\s]", "")
                .cast(pl.Utf8)
                .alias("TIPO DE ACTIVIDAD")
            ),
        ])

    # ── Date normalization ────────────────────────────────────────────────

    def _normalize_fecha(self, df: pl.DataFrame) -> pl.DataFrame:
        from datetime import date, timedelta

        fecha_limite = date.today().replace(day=1) - timedelta(days=1)
        col = "Fecha Ingreso"

        if df[col].dtype != pl.Utf8:
            df = df.with_columns(pl.col(col).cast(pl.Utf8).alias(col))

        unique_vals = df[col].unique().to_list()
        fecha_map = {}
        advertencias = []
        for val in unique_vals:
            formatted, warn = self._parse_fecha(val, fecha_limite)
            fecha_map[val] = formatted
            if warn:
                advertencias.append(f"Fecha '{val}' → {formatted}: {warn}")

        if advertencias:
            self.logger.warning(
                f"{len(advertencias)} fecha(s) fuera del periodo de 3 meses:\n" + "\n".join(f"  {a}" for a in advertencias),
            )

        return df.with_columns(
            pl.col(col).replace(fecha_map).alias(col)
        )

    @staticmethod
    def _parse_fecha(val, fecha_limite) -> tuple[str, str]:
        """Retorna (fecha_formateada, advertencia o '')."""
        from datetime import date as dt_date
        if val is None or str(val).strip() in ("", "None", "null", "nan", "NaN"):
            return "", ""
        s = str(val).strip().split(" ")[0]  # quitar hora

        # Si ya es dd/mm/yyyy
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                try:
                    fecha = dt_date(int(parts[2]), int(parts[1]), int(parts[0]))
                    warn = _fecha_warning(fecha, fecha_limite)
                    return s, warn
                except ValueError:
                    return "", ""

        # Formato yyyy-mm-dd
        if "-" in s:
            parts = s.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                try:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    fecha = dt_date(y, m, d)
                    if fecha <= fecha_limite:
                        warn = _fecha_warning(fecha, fecha_limite)
                        return fecha.strftime("%d/%m/%Y"), warn
                    # Fecha > limite: swap día/mes solo si resultado cae en mes de trabajo
                    if d <= 12:
                        try:
                            fecha_swap = dt_date(y, d, m)
                            if fecha_swap <= fecha_limite and fecha_swap.month == fecha_limite.month:
                                warn = _fecha_warning(fecha_swap, fecha_limite)
                                return fecha_swap.strftime("%d/%m/%Y"), warn
                        except ValueError:
                            pass
                    # Swap no aplica: devolver fecha original con advertencia
                    warn = _fecha_warning(fecha, fecha_limite)
                    return fecha.strftime("%d/%m/%Y"), warn
                except ValueError:
                    try:
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        fecha_swap = dt_date(y, d, m)
                        warn = _fecha_warning(fecha_swap, fecha_limite)
                        return fecha_swap.strftime("%d/%m/%Y"), warn
                    except ValueError:
                        return "", ""
        return "", ""

    # ── TIAN: redirección de facturación (spec 008 RF-12..20) ──────────────

    def _apply_tian(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        """Redirige a facturarse bajo TIAN_NIT las filas cuyo NIT está en la
        tabla `tian`, ANTES de asignar facturador/paquete/tarifas (RF-13), de
        modo que hereden los de TIAN.

        Va después de _normalize_columns (RF-09 del plan): pl_normalize_name
        borra los paréntesis, así que el sufijo "(TIAN)" solo puede aplicarse
        una vez la razón social ya quedó normalizada."""
        tian_nit = lookups.get("tian_nit", "")
        if not tian_nit:
            self.logger.error(
                "TIAN: variable de entorno TIAN_NIT no está definida; se omite la redirección.",
            )
            return df

        nit_to_company = lookups["nit_to_company"]
        tian_company = nit_to_company.get(tian_nit)
        if not tian_company:
            self.logger.error(
                f"TIAN: el NIT {tian_nit} (TIAN_NIT) no existe en companies; se aborta la redirección.",
            )
            return df

        company_to_package = lookups["company_to_package"]
        if tian_company["id"] not in company_to_package:
            self.logger.error(
                f"TIAN: la empresa {tian_nit} no tiene paquete asignado; se aborta la redirección.",
            )
            return df

        tian_nits = lookups.get("tian_nits", set())
        if not tian_nits:
            return df

        raw_source = "_NIT_RAW" if "_NIT_RAW" in df.columns else "NIT"
        raw_nits = df[raw_source].cast(pl.Utf8).str.replace_all(r"[^\d]", "").to_list()
        current_nits = df["NIT"].cast(pl.Utf8).to_list()
        empresas = df["Empresa"].cast(pl.Utf8).to_list()

        nuevos_nit = list(current_nits)
        nuevas_empresas = list(empresas)
        asignaciones: dict[str, TianAssignment] = {}

        for i, nit_actual in enumerate(current_nits):
            if nit_actual in tian_nits:
                candidato = nit_actual
            elif raw_nits[i] in tian_nits:
                candidato = raw_nits[i]
            else:
                continue
            if candidato == tian_nit:
                continue

            nit_original = nit_actual
            empresa_original = empresas[i]
            name_canonica = nit_to_company.get(nit_original, {}).get("name") or empresa_original
            name_final = name_canonica if name_canonica.endswith("(TIAN)") else f"{name_canonica}(TIAN)"

            nuevos_nit[i] = tian_nit
            nuevas_empresas[i] = name_final

            if nit_original in asignaciones:
                previa = asignaciones[nit_original]
                asignaciones[nit_original] = TianAssignment(
                    nit_original=previa.nit_original,
                    name_original=previa.name_original,
                    nit_tian=tian_nit,
                    name_final=name_final,
                    rows=previa.rows + 1,
                )
            else:
                asignaciones[nit_original] = TianAssignment(
                    nit_original=nit_original,
                    name_original=empresa_original,
                    nit_tian=tian_nit,
                    name_final=name_final,
                    rows=1,
                )

        if not asignaciones:
            return df

        lookups["tian_rerouted_nits"] = {tian_nit}

        df = df.with_columns([
            pl.Series("NIT", nuevos_nit),
            pl.Series("Empresa", nuevas_empresas),
        ])

        if self.tian_log_generator:
            self.tian_log_generator.generate(list(asignaciones.values()), self.logs_dir)

        return df

    # ── City normalization with pre-computed fuzzy ─────────────────────────

    def _normalize_city(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        cities_all = lookups["cities_all"]
        unique_cities = df["Ciudad"].unique().to_list()

        # Fuzzy match only unique values
        city_map = {}
        for city in unique_cities:
            if city is None:
                city_map[city] = city
                continue
            upper = str(city).upper()
            result = self.fuzz.fuzz_property(upper, cities_all)
            city_map[city] = result if result else upper

        return df.with_columns(
            pl.col("Ciudad").replace(city_map).alias("Ciudad")
        )

    # ── Assign FACTURADOR via join ────────────────────────────────────────

    def _assign_facturador(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_biller = lookups["company_to_biller"]
        biller_id_to_name = lookups["biller_id_to_name"]

        # Build NIT → facturador_name mapping
        nit_to_facturador = {}
        for nit, comp in nit_to_company.items():
            biller_id = company_to_biller.get(comp["id"])
            if biller_id:
                name = biller_id_to_name.get(biller_id, "GENERAL")
                nit_to_facturador[nit] = name
            else:
                nit_to_facturador[nit] = "GENERAL"

        # Build lookup DataFrame and join
        if nit_to_facturador:
            df_fact = pl.DataFrame({
                "NIT": list(nit_to_facturador.keys()),
                "FACTURADOR": list(nit_to_facturador.values()),
            })
            df = df.join(df_fact, on="NIT", how="left").with_columns(
                pl.col("FACTURADOR").fill_null("GENERAL")
            )
        else:
            df = df.with_columns(pl.lit("GENERAL").alias("FACTURADOR"))

        df = df.with_columns(
            pl.when(pl.col("FACTURADOR") == "GENERAL")
            .then(pl.lit("GENERAL"))
            .otherwise(pl.lit("ESPECIAL"))
            .alias("Especial / General")
        )
        return df

    # ── Assign PAQUETE via join ───────────────────────────────────────────

    def _assign_paquete(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_package = lookups["company_to_package"]
        packages_all = lookups["packages_all"]

        default_package = "PAQUETE C 2025"

        # Build NIT → package_name mapping
        nit_to_pkg = {}
        for nit, comp in nit_to_company.items():
            pkg_tuple = company_to_package.get(comp["id"])
            if pkg_tuple:
                pkg_id, model = pkg_tuple
                if model == Package.__name__:
                    name = next((p["name"] for p in packages_all if p["id"] == pkg_id), None)
                elif model == Provider.__name__:
                    name = next((p["name"] for p in self.provider_repo.all() if p["id"] == pkg_id), None)
                elif model == Special.__name__:
                    name = next((p["name"] for p in self.special_repo.all() if p["id"] == pkg_id), None)
                else:
                    name = None
                nit_to_pkg[nit] = name or default_package
            else:
                nit_to_pkg[nit] = default_package

        if nit_to_pkg:
            df_pkg = pl.DataFrame({
                "NIT": list(nit_to_pkg.keys()),
                "PAQUETE": list(nit_to_pkg.values()),
            })
            df = df.join(df_pkg, on="NIT", how="left")
        else:
            df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias("PAQUETE"))

        df = df.with_columns(pl.col("PAQUETE").fill_null(default_package))

        # PAQUETE muestra la tarifa de Odoo (especial, si no base); la cascada
        # local sigue leyendo el paquete local desde _PAQUETE_LOCAL (spec 010, RF-08).
        df = df.with_columns(pl.col("PAQUETE").alias("_PAQUETE_LOCAL"))
        odoo_names = {
            nit: p["special_name"] or p["base_name"]
            for nit, p in self._odoo_by_nit.items()
            if p["special_name"] or p["base_name"]
        }
        if odoo_names:
            df_odoo = pl.DataFrame({
                "NIT": list(odoo_names.keys()),
                "_PAQUETE_ODOO": list(odoo_names.values()),
            })
            df = (
                df.join(df_odoo, on="NIT", how="left")
                .with_columns(pl.coalesce("_PAQUETE_ODOO", "_PAQUETE_LOCAL").alias("PAQUETE"))
                .drop("_PAQUETE_ODOO")
            )

        return df

    # ── Tarifas de Odoo (especial → base) ─────────────────────────────────

    def _resolve_odoo_cells(self, rows_data: list[dict], headers: list) -> dict[tuple[str, int], int]:
        """Precio de Odoo por celda (columna CUP, fila): tarifa especial y luego base."""
        resolved: dict[tuple[str, int], int] = {}
        if not self.odoo_available:
            return resolved
        for idx, row in enumerate(rows_data):
            partner = self._odoo_by_nit.get(row["NIT"])
            if not partner:
                continue
            for h in headers:
                if row.get(str(h)) != 1:
                    continue
                for rate_id in (partner["special_id"], partner["base_id"]):
                    price = self._odoo_index.price(
                        rate_id, row["Ciudad"], str(h).strip(), row["TIPO DE ACTIVIDAD"]
                    )
                    if price:
                        resolved[(str(h), idx)] = price
                        break
        return resolved

    # ── Assign rates with batch query ─────────────────────────────────────

    def _assign_rates(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        company_to_package = lookups["company_to_package"]
        city_name_to_id = lookups["city_name_to_id"]
        cup_code_to_id = lookups["cup_code_to_id"]
        activity_name_to_id = lookups["activity_name_to_id"]
        package_name_to_id = lookups["package_name_to_id"]
        packages_all = lookups["packages_all"]

        # Reverse lookups for logging
        city_id_to_name = {v: k for k, v in city_name_to_id.items()}
        activity_id_to_name = {v: k for k, v in activity_name_to_id.items()}

        default_package = "PAQUETE C 2025"
        default_pkg_tuple = package_name_to_id.get(default_package)

        headers = [h for h in df.columns if str(h).replace("-", "").isdigit()]

        # Cast CUP columns to Int64
        for h in headers:
            df = df.with_columns(pl.col(str(h)).cast(pl.Int64))

        # Phase 1: Collect all unique rate keys needed
        rate_keys_set = set()
        local_pkg_col = "_PAQUETE_LOCAL" if "_PAQUETE_LOCAL" in df.columns else "PAQUETE"
        report_cols = [c for c in ("Empresa", "Paciente", "N° Identificación") if c in df.columns]
        rows_data = df.select(
            ["NIT", "Ciudad", "TIPO DE ACTIVIDAD", pl.col(local_pkg_col).alias("PAQUETE")]
            + report_cols
            + [str(h) for h in headers]
        ).to_dicts()
        odoo_resolved = self._resolve_odoo_cells(rows_data, headers)
        self._odoo_cells = len(odoo_resolved)
        self._findings = {key: [] for key in PHASE_FINDING_KEYS}

        def record(phase_key: str, idx: int, h, price, origin: str) -> None:
            row = rows_data[idx]
            self._findings[phase_key].append({
                "NIT": row["NIT"],
                "Empresa": row.get("Empresa"),
                "Paciente": row.get("Paciente"),
                "N° Identificación": row.get("N° Identificación"),
                "Ciudad": row["Ciudad"],
                "TIPO DE ACTIVIDAD": row["TIPO DE ACTIVIDAD"],
                "CUP": str(h),
                "Precio asignado": int(price),
                "Origen": origin,
            })

        with self.progress("Calculando tarifas", total=len(rows_data)):
            for idx, row in enumerate(rows_data):
                nit = row["NIT"]
                city = row["Ciudad"]
                activity = row["TIPO DE ACTIVIDAD"]
                pkg_name = row["PAQUETE"]

                comp = nit_to_company.get(nit)
                pkg_tuple = company_to_package.get(comp["id"]) if comp else None

                if pkg_tuple:
                    package_id, model = pkg_tuple
                elif pkg_name and pkg_name in package_name_to_id:
                    package_id, model = package_name_to_id[pkg_name]
                else:
                    self.progress.advance()
                    continue

                city_id = city_name_to_id.get(city)
                activity_id = activity_name_to_id.get(activity)

                if not all([package_id, city_id, activity_id]):
                    self.progress.advance()
                    continue

                for h in headers:
                    if row.get(str(h)) == 1 and (str(h), idx) not in odoo_resolved:
                        cup_id = cup_code_to_id.get(str(h).strip())
                        if cup_id:
                            rate_keys_set.add((package_id, city_id, cup_id, activity_id, model))
                            if default_pkg_tuple:
                                def_id, def_model = default_pkg_tuple
                                rate_keys_set.add((def_id, city_id, cup_id, activity_id, def_model))
                                # Also add base CUP key for homologation fallback
                                base_code = str(h).split("-")[0]
                                if base_code != str(h):
                                    base_cup_id = cup_code_to_id.get(base_code)
                                    if base_cup_id:
                                        rate_keys_set.add((def_id, city_id, base_cup_id, activity_id, def_model))

                self.progress.advance()

        # Phase 2: Batch query all needed rates
        self.logger.info(
            f"Consultando {len(rate_keys_set)} combinaciones únicas de tarifas",
        )
        rates_cache = self.rates_repo.find_batch(list(rate_keys_set))
        self.logger.info(
            f"Encontradas {len(rates_cache)} tarifas de {len(rate_keys_set)} consultadas",
        )

        # Phase 3: Build result columns with fallback, collect unresolved for wildcard
        result_cols = {str(h): df[str(h)].to_list() for h in headers}
        for (col, idx), price in odoo_resolved.items():
            result_cols[col][idx] = price
        # cell_colors[(col, row_idx)] = hex color — populated per fallback phase
        cell_colors: dict[tuple[str, int], str] = {}
        _COLOR_PHASE2 = "FFF2CC"   # Dorado suave — PAQUETE C 2025, mismo CUP
        _COLOR_PHASE3 = "F4B183"   # Naranja profesional — cualquier paquete, mismo CUP, misma ciudad
        _COLOR_PHASE4 = "BDD7EE"   # Azul acero claro — PAQUETE C 2025, CUP base
        _COLOR_PHASE5 = "9DC3E6"   # Azul medio — cualquier paquete, CUP base, misma ciudad
        _COLOR_PHASE6 = "D5A6E6"   # Púrpura medio — cualquier paquete, otra ciudad (cup+actividad)
        _COLOR_PHASE7 = "FFB6C1"   # Rosa     — cualquier paquete, otra ciudad (cup+actividad)
        fallback_logs = []
        unresolved = []  # list of (idx, h, city_id, cup_id, activity_id, pkg_name, city, activity)

        for idx, row in enumerate(rows_data):
            nit = row["NIT"]
            city = row["Ciudad"]
            activity = row["TIPO DE ACTIVIDAD"]
            pkg_name = row["PAQUETE"]

            comp = nit_to_company.get(nit)
            pkg_tuple = company_to_package.get(comp["id"]) if comp else None

            if pkg_tuple:
                package_id, model = pkg_tuple
            elif pkg_name and pkg_name in package_name_to_id:
                package_id, model = package_name_to_id[pkg_name]
            else:
                continue

            city_id = city_name_to_id.get(city)
            activity_id = activity_name_to_id.get(activity)

            if not all([package_id, city_id, activity_id]):
                continue

            for h in headers:
                if row.get(str(h)) == 1:
                    cup_id = cup_code_to_id.get(str(h).strip())
                    if cup_id:
                        key = (package_id, city_id, cup_id, activity_id, model)
                        price = rates_cache.get(key)
                        if price:
                            result_cols[str(h)][idx] = int(price)
                        elif default_pkg_tuple:
                            def_id, def_model = default_pkg_tuple
                            fallback_key = (def_id, city_id, cup_id, activity_id, def_model)
                            fallback_price = rates_cache.get(fallback_key)
                            if fallback_price:
                                result_cols[str(h)][idx] = int(fallback_price)
                                cell_colors[(str(h), idx)] = _COLOR_PHASE2
                                fallback_logs.append(
                                    f"'{pkg_name}' no cuenta con tarifa para CUP '{h}' en la ciudad '{city}' "
                                    f"para la actividad '{activity}', se asignó tarifa del paquete '{default_package}'"
                                )
                            else:
                                unresolved.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))
                        else:
                            unresolved.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))

        # Phase 4: Wildcard fallback — find any rate for unresolved combinations
        still_unresolved = []
        if unresolved:
            wildcard_keys = list({(city_id, cup_id, act_id) for _, _, city_id, cup_id, act_id, _, _, _ in unresolved})
            wildcard_cache = self.rates_repo.find_any_rate(wildcard_keys)

            # Build id→name maps for logging
            pkg_id_to_name = {p["id"]: p["name"] for p in packages_all}
            prov_id_to_name = {p["id"]: p["name"] for p in self.provider_repo.all()}
            spec_id_to_name = {p["id"]: p["name"] for p in self.special_repo.all()}

            wildcard_logs = []
            for idx, h, city_id, cup_id, activity_id, pkg_name, city, activity in unresolved:
                result_tuple = wildcard_cache.get((city_id, cup_id, activity_id))
                if result_tuple:
                    w_rate, w_type, w_id = result_tuple
                    result_cols[str(h)][idx] = int(w_rate)
                    cell_colors[(str(h), idx)] = _COLOR_PHASE3
                    # Resolve source name
                    if w_type == "Package":
                        source = pkg_id_to_name.get(w_id, str(w_id))
                    elif w_type == "Provider":
                        source = prov_id_to_name.get(w_id, str(w_id))
                    else:
                        source = spec_id_to_name.get(w_id, str(w_id))
                    wildcard_logs.append(
                        f"'{pkg_name}' no cuenta con tarifa para CUP '{h}' en la ciudad '{city}' "
                        f"para la actividad '{activity}', se asignó tarifa del paquete '{source}'"
                    )
                else:
                    still_unresolved.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))

            if wildcard_logs:
                unique_wlogs = sorted(set(wildcard_logs))
                self.logger.warning(
                    f"{len(wildcard_logs)} tarifas asignadas desde otros paquetes:\n"
                    + "\n".join(f"  {l}" for l in unique_wlogs[:50]),
                    user_msg=f"{len(wildcard_logs)} tarifas tomadas de otros paquetes por falta de tarifa.",
                )

        # Phase 5: CUP homologation — strip suffix and search base CUP in PAQUETE C 2025
        still_unresolved_2 = []
        if still_unresolved and default_pkg_tuple:
            def_id, def_model = default_pkg_tuple
            homolog_logs = []
            for idx, h, city_id, cup_id, activity_id, pkg_name, city, activity in still_unresolved:
                base_code = str(h).split("-")[0]
                if base_code == str(h):
                    still_unresolved_2.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))
                    continue  # No dash — nothing to homologate here
                base_cup_id = cup_code_to_id.get(base_code)
                if not base_cup_id:
                    still_unresolved_2.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))
                    continue
                homolog_key = (def_id, city_id, base_cup_id, activity_id, def_model)
                homolog_price = rates_cache.get(homolog_key)
                if homolog_price:
                    result_cols[str(h)][idx] = int(homolog_price)
                    cell_colors[(str(h), idx)] = _COLOR_PHASE4
                    homolog_logs.append(
                        f"'{pkg_name}' no cuenta con tarifa para CUP '{h}' en la ciudad '{city}' "
                        f"para la actividad '{activity}', se homologó al CUP '{base_code}' "
                        f"del paquete '{default_package}'"
                    )
                else:
                    still_unresolved_2.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))

            if homolog_logs:
                unique_hlogs = sorted(set(homolog_logs))
                self.logger.warning(
                    f"{len(homolog_logs)} tarifas homologadas al CUP base en '{default_package}':\n"
                    + "\n".join(f"  {l}" for l in unique_hlogs[:50]),
                    user_msg=f"{len(homolog_logs)} tarifas homologadas al CUP base del paquete '{default_package}'.",
                )
        else:
            still_unresolved_2 = list(still_unresolved)

        # Phase 6: CUP homologation in any package — base CUP wildcard
        still_unresolved_3 = []
        if still_unresolved_2:
            wildcard2_keys = set()
            for _, h, city_id, _, activity_id, _, _, _ in still_unresolved_2:
                base_code = str(h).split("-")[0]
                if base_code == str(h):
                    continue  # No dash — will go to Phase 7
                base_cup_id = cup_code_to_id.get(base_code)
                if base_cup_id:
                    wildcard2_keys.add((city_id, base_cup_id, activity_id))

            if wildcard2_keys:
                wildcard2_cache = self.rates_repo.find_any_rate(list(wildcard2_keys))

                pkg_id_to_name = {p["id"]: p["name"] for p in packages_all}
                prov_id_to_name = {p["id"]: p["name"] for p in self.provider_repo.all()}
                spec_id_to_name = {p["id"]: p["name"] for p in self.special_repo.all()}

                wildcard2_logs = []
                for idx, h, city_id, cup_id, activity_id, pkg_name, city, activity in still_unresolved_2:
                    base_code = str(h).split("-")[0]
                    if base_code == str(h):
                        still_unresolved_3.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))
                        continue
                    base_cup_id = cup_code_to_id.get(base_code)
                    if not base_cup_id:
                        still_unresolved_3.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))
                        continue
                    result_tuple = wildcard2_cache.get((city_id, base_cup_id, activity_id))
                    if result_tuple:
                        w_rate, w_type, w_id = result_tuple
                        result_cols[str(h)][idx] = int(w_rate)
                        cell_colors[(str(h), idx)] = _COLOR_PHASE5
                        if w_type == "Package":
                            source = pkg_id_to_name.get(w_id, str(w_id))
                        elif w_type == "Provider":
                            source = prov_id_to_name.get(w_id, str(w_id))
                        else:
                            source = spec_id_to_name.get(w_id, str(w_id))
                        wildcard2_logs.append(
                            f"'{pkg_name}' no cuenta con tarifa para CUP '{h}' en la ciudad '{city}' "
                            f"para la actividad '{activity}', se homologó al CUP '{base_code}' "
                            f"del paquete '{source}'"
                        )
                    else:
                        still_unresolved_3.append((idx, h, city_id, cup_id, activity_id, pkg_name, city, activity))

                if wildcard2_logs:
                    unique_w2logs = sorted(set(wildcard2_logs))
                    self.logger.warning(
                        f"{len(wildcard2_logs)} tarifas homologadas al CUP base en cualquier paquete:\n"
                        + "\n".join(f"  {l}" for l in unique_w2logs[:50]),
                        user_msg=f"{len(wildcard2_logs)} tarifas homologadas al CUP base desde otros paquetes.",
                    )
            else:
                still_unresolved_3 = list(still_unresolved_2)

        # Phase 7: Any package, any city — search by cup_id + activity_id only
        if still_unresolved_3:
            cup_activity_keys = list({(cup_id, activity_id) for _, _, _, cup_id, activity_id, _, _, _ in still_unresolved_3})
            cup_activity_cache = self.rates_repo.find_rate_by_cup_activity(cup_activity_keys)

            if cup_activity_cache:
                if 'pkg_id_to_name' not in dir():
                    pkg_id_to_name = {p["id"]: p["name"] for p in packages_all}
                    prov_id_to_name = {p["id"]: p["name"] for p in self.provider_repo.all()}
                    spec_id_to_name = {p["id"]: p["name"] for p in self.special_repo.all()}

                phase7_logs = []
                for idx, h, city_id, cup_id, activity_id, pkg_name, city, activity in still_unresolved_3:
                    result_tuple = cup_activity_cache.get((cup_id, activity_id))
                    if result_tuple:
                        w_rate, w_type, w_id = result_tuple
                        result_cols[str(h)][idx] = int(w_rate)
                        cell_colors[(str(h), idx)] = _COLOR_PHASE6
                        if w_type == "Package":
                            source = pkg_id_to_name.get(w_id, str(w_id))
                        elif w_type == "Provider":
                            source = prov_id_to_name.get(w_id, str(w_id))
                        else:
                            source = spec_id_to_name.get(w_id, str(w_id))
                        phase7_logs.append(
                            f"'{pkg_name}' no cuenta con tarifa para CUP '{h}' en la ciudad '{city}', "
                            f"se asignó tarifa del paquete '{source}' (ciudad diferente)"
                        )

                if phase7_logs:
                    unique_p7logs = sorted(set(phase7_logs))
                    self.logger.warning(
                        f"{len(phase7_logs)} tarifas asignadas desde cualquier ciudad/paquete:\n"
                        + "\n".join(f"  {l}" for l in unique_p7logs[:50]),
                        user_msg=f"{len(phase7_logs)} tarifas tomadas de otra ciudad por falta de tarifa local.",
                    )

        if fallback_logs:
            unique_logs = sorted(set(fallback_logs))
            self.logger.warning(
                f"{len(fallback_logs)} tarifas asignadas desde paquete por defecto:\n"
                + "\n".join(f"  {l}" for l in unique_logs[:50]),
                user_msg=f"{len(fallback_logs)} tarifas tomadas del paquete '{default_package}' por falta de tarifa en el paquete original.",
            )

        # Replace columns with computed values
        for h in headers:
            df = df.with_columns(pl.Series(str(h), result_cols[str(h)]).cast(pl.Int64))

        # Total column
        if headers:
            df = df.with_columns(
                pl.sum_horizontal([pl.col(str(h)) for h in headers]).alias("Total")
            )
        else:
            df = df.with_columns(pl.lit(0).alias("Total"))

        self.logger.info(
            f"Columna Total generada: {len(headers)} columnas CUP, {df.height} filas",
            user_msg=f"Columna Total calculada para {df.height} registros.",
        )
        return df, cell_colors

    # ── Validate Empresa matches DB ───────────────────────────────────────

    def _validate_empresa(self, df: pl.DataFrame, lookups: dict) -> pl.DataFrame:
        nit_to_company = lookups["nit_to_company"]
        odoo_resolved_nits = lookups.get("odoo_resolved_nits", set())
        tian_rerouted_nits = lookups.get("tian_rerouted_nits", set())

        # Odoo tiene prioridad sobre BD local (ver cascada en _match_companies);
        # los NIT ya resueltos vía Odoo no deben revertirse al nombre de BD local.
        # Los NIT redirigidos a TIAN (spec 008 RF-13) tampoco: su Empresa lleva
        # el sufijo "(TIAN)" con la razón social original, no la de TIAN.
        excluidos = odoo_resolved_nits | tian_rerouted_nits
        db_nit_to_name = {
            nit: normalize_name(c["name"])
            for nit, c in nit_to_company.items()
            if nit not in excluidos
        }

        # Check mismatches
        mismatches = 0
        for row in df.iter_rows(named=True):
            nit = row["NIT"]
            if nit and nit in db_nit_to_name and row["Empresa"] != db_nit_to_name[nit]:
                mismatches += 1

        if mismatches:
            self.logger.warning(
                f"{mismatches} empresas no coinciden con BD. Corrigiendo.",
                user_msg=f"{mismatches} nombres de empresa corregidos según la base de datos.",
            )
            df = df.with_columns(
                pl.struct(["NIT", "Empresa"])
                .map_elements(
                    lambda s: db_nit_to_name.get(s["NIT"], s["Empresa"]),
                    return_dtype=pl.Utf8,
                )
                .alias("Empresa")
            )

        return df
