"""Opción 6: carga desde Excel de las empresas que se facturan a otro NIT (TIAN, VISE, RSG…).

Plantilla (fila 1 = encabezados; mayúsculas/espacios indiferentes):
  NIT_ORIGEN | NIT_DESTINO | ETIQUETA | NOMBRE (opcional) | ACTIVO (opcional)
Cada fila válida se crea o actualiza en `billing_redirects` (TIAN incluido, como una
etiqueta más). Las filas que no vienen en el archivo no se tocan; ACTIVO=NO desactiva.
La opción 3 (Asignar Tarifas) aplica estas redirecciones: la fila de NIT_ORIGEN se factura
bajo NIT_DESTINO con la Empresa "<razón social>(<ETIQUETA>)".
"""

import re

import polars as pl

from src.shared.reporting.findings_writer import summarize_findings

COLUMNAS_REQUERIDAS = ("NIT_ORIGEN", "NIT_DESTINO", "ETIQUETA")
ETIQUETA_MAX = 50
_INACTIVO = {"NO", "N", "0", "FALSE", "FALSO", "INACTIVO"}

FINDING_COLUMNS = {
    "filas_con_error": ["Fila", "NIT origen", "NIT destino", "Etiqueta", "Motivo"],
    "filas_repetidas": ["Fila", "NIT origen", "Fila que queda"],
    "destinos_por_revisar": ["NIT destino", "Etiqueta", "Empresas", "Motivo"],
    "origenes_en_tian": ["NIT origen", "Etiqueta", "Motivo"],
    "desactivadas": ["NIT origen", "Resultado"],
}


def _columna(nombre: str) -> str:
    return re.sub(r"\s+", "_", str(nombre).strip().upper())


def _texto(v) -> str:
    return "" if v is None else str(v).strip()


def _nit(v) -> tuple[str, str | None]:
    """NIT solo con dígitos. Se aceptan puntos, guiones, comas y espacios; un '.0' final
    (número leído de Excel) se quita. Devuelve (nit, error)."""
    texto = _texto(v)
    if texto.endswith(".0"):
        texto = texto[:-2]
    if not texto:
        return "", "vacío"
    if re.search(r"[^\d.\-,\s]", texto):
        return "", f"'{texto}' tiene caracteres que no son dígitos"
    return re.sub(r"\D", "", texto), None


class ImportBillingRedirectsFromExcel:
    def __init__(self, redirect_repo, company_repo, biller_company_repo, tian_repo,
                 findings_writer, logger, tian_nit: str = ""):
        self.redirect_repo = redirect_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.tian_repo = tian_repo
        self.findings_writer = findings_writer
        self.logger = logger
        self.tian_nit = re.sub(r"\D", "", tian_nit or "")

    def execute(self, df: pl.DataFrame) -> dict | None:
        df = df.rename({c: _columna(c) for c in df.columns})
        faltan = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltan:
            self.logger.error(
                f"Plantilla de redirecciones sin columnas: {faltan}",
                user_msg=("La hoja debe tener las columnas NIT_ORIGEN, NIT_DESTINO y ETIQUETA "
                          f"(faltan: {', '.join(faltan)}). No se cargó nada."),
            )
            return None

        books = {k: [] for k in FINDING_COLUMNS}
        validas: dict[str, dict] = {}       # nit_origen → fila (la última gana)
        fila_de: dict[str, int] = {}
        a_desactivar: list[str] = []

        for i, row in enumerate(df.iter_rows(named=True)):
            fila = i + 2  # fila 1 = encabezados
            if all(_texto(v) == "" for v in row.values()):
                continue
            origen, err_o = _nit(row.get("NIT_ORIGEN"))
            destino, err_d = _nit(row.get("NIT_DESTINO"))
            etiqueta = _texto(row.get("ETIQUETA")).upper()
            nombre = _texto(row.get("NOMBRE")) or None
            inactivo = _texto(row.get("ACTIVO")).upper() in _INACTIVO

            def error(motivo):
                books["filas_con_error"].append({
                    "Fila": fila, "NIT origen": _texto(row.get("NIT_ORIGEN")),
                    "NIT destino": _texto(row.get("NIT_DESTINO")), "Etiqueta": etiqueta, "Motivo": motivo,
                })

            if err_o:
                error(f"NIT origen {err_o}")
                continue
            if inactivo:
                a_desactivar.append(origen)
                continue
            if err_d:
                error(f"NIT destino {err_d}")
                continue
            if not etiqueta:
                error("Falta la etiqueta")
                continue
            if len(etiqueta) > ETIQUETA_MAX:
                error(f"La etiqueta tiene {len(etiqueta)} caracteres; el máximo es {ETIQUETA_MAX}")
                continue
            if origen == destino:
                error("El NIT origen y el destino son el mismo")
                continue
            if self.tian_nit and origen == self.tian_nit:
                error("El NIT origen es el de TIAN (TIAN_NIT): no se puede redirigir")
                continue
            if origen in validas:
                books["filas_repetidas"].append({"Fila": fila_de[origen], "NIT origen": origen, "Fila que queda": fila})
            validas[origen] = {"nit_origen": origen, "nit_destino": destino, "etiqueta": etiqueta, "name": nombre}
            fila_de[origen] = fila

        self._revisar_destinos(list(validas.values()), books)
        self._revisar_tian(list(validas.values()), books)

        nuevas = actualizadas = 0
        if validas:
            resultado = self.redirect_repo.upsert_many(list(validas.values()))
            if resultado is None:
                return None
            nuevas, actualizadas = resultado
        desactivadas = []
        if a_desactivar:
            desactivadas = self.redirect_repo.deactivate(a_desactivar)
            if desactivadas is None:
                return None
            for nit in a_desactivar:
                books["desactivadas"].append({
                    "NIT origen": nit,
                    "Resultado": "Desactivada" if nit in desactivadas else "No estaba activa: sin cambios",
                })

        folder = self.findings_writer.write(books, FINDING_COLUMNS) if any(books.values()) else None
        resumen = {
            "nuevas": nuevas, "actualizadas": actualizadas, "desactivadas": len(desactivadas),
            "errores": len(books["filas_con_error"]),
        }
        self.logger.info(
            f"Redirecciones cargadas: {resumen}",
            user_msg=(f"Empresas facturadas a otro NIT: {nuevas} nuevas, {actualizadas} actualizadas, "
                      f"{len(desactivadas)} desactivadas, {len(books['filas_con_error'])} filas con error. "
                      + summarize_findings(books, folder)),
        )
        return resumen

    def _revisar_destinos(self, filas, books):
        """Destinos que no van a funcionar en la opción 3 (o que facturan en GENERAL)."""
        if not filas:
            return
        companies = self.company_repo.all() or []
        por_nit = {c["nit"]: c for c in companies}
        con_paquete = {p["company"] for p in (self.company_repo.companies_packages_all() or [])}
        con_facturador = {b["company"] for b in (self.biller_company_repo.all() or [])}
        grupos: dict[tuple, int] = {}
        for f in filas:
            grupos[(f["nit_destino"], f["etiqueta"])] = grupos.get((f["nit_destino"], f["etiqueta"]), 0) + 1
        for (destino, etiqueta), n in sorted(grupos.items()):
            empresa = por_nit.get(destino)
            if empresa is None:
                motivo = "No existe en la BD (companies): sus empresas no se redirigen hasta crearla"
            elif empresa["id"] not in con_paquete:
                motivo = "No tiene paquete: sus empresas no se redirigen hasta asignarle uno"
            elif empresa["id"] not in con_facturador:
                motivo = "No tiene facturador: sus pre-facturas saldrán en GENERAL"
            else:
                continue
            books["destinos_por_revisar"].append(
                {"NIT destino": destino, "Etiqueta": etiqueta, "Empresas": n, "Motivo": motivo})

    def _revisar_tian(self, filas, books):
        if not filas or not self.tian_repo:
            return
        en_tian = {re.sub(r"\D", "", str(r["nit_error"])) for r in (self.tian_repo.all() or [])}
        for f in filas:
            if f["nit_origen"] in en_tian:
                books["origenes_en_tian"].append({
                    "NIT origen": f["nit_origen"], "Etiqueta": f["etiqueta"],
                    "Motivo": "También está en la tabla tian, que tiene prioridad: esta fila no se aplica mientras siga allí",
                })
