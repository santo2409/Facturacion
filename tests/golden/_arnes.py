"""Arnés del golden master: ejecuta los controllers reales de cada opción del menú
sobre entradas fijas y devuelve una instantánea (dict JSON) de todo lo que producen.

Qué es real y qué se sustituye (fronteras externas, sin tocar código de producción):
- Real: controllers, casos de uso, servicios de dominio, lectura/escritura de Excel,
  generadores de libros, `XmlRpcOdooRepository`, `SaCompanyNitCacheRepository`.
- Sustituido con monkeypatch:
  · preguntas al usuario (`ask_excel_path`, `ask_sheet_name`, `ask_directory_path`);
  · PostgreSQL: `get_session` y los `Sa*Repository` → repositorios en memoria
    sembrados desde `entradas/<escenario>/bd.json`;
  · Odoo: `xmlrpc.client.ServerProxy` → `OdooSimulado` (ver _odoo_simulado.py);
  · RUES: `RuesPlaywrightScraper` → `FakeNitScraper` sembrado desde `rues.json`;
  · reloj: fecha y hora de ejecución fijas (FECHA_EJECUCION).

Ver README.md para la lista completa de normalizaciones y su justificación.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import types
import xmlrpc.client
from datetime import date, datetime
from pathlib import Path

import openpyxl
from rich.console import Console

# Importar TODO antes de controlar el entorno: varios módulos ejecutan
# load_dotenv(override=True) al importarse y pisarían las variables fijadas.
import main  # noqa: E402
from src.assign.application.use_cases.assigned_rates import AssignRatesFromExcel
from src.assign.infrastructure.console import assigned_rates_controller as ctrl_opcion6
from src.assign.infrastructure.reporting.xlsx_phase_findings_reporter import XlsxPhaseFindingsReporter
from src.billers.infrastructure.console import import_billers_controller as ctrl_opcion2
from src.dataProcessing.infrastructure.console import import_information_controller as ctrl_opcion3
from src.dataProcessing.infrastructure.persistence.cup_column_validator import _is_success
from src.odooInjection.domain.services.city_account_resolver import CityAccountResolver
from src.odooInjection.infrastructure.console import inject_invoices_controller as ctrl_opcion8
from src.preInvoice.infrastructure.console import pre_invoice_controller as ctrl_opcion7
from src.rates.infrastructure.console import import_rates_controller as ctrl_opcion4
from src.scrapping.domain.entities.nit_result import NitResult
from src.scrapping.infrastructure.console import import_rues_nits as ctrl_opcion1
from src.scrapping.infrastructure.console import nit_service
from src.shared.reporting.xlsx_findings_writer import XlsxFindingsWriter
from src.shared.utils.document_normalizer import normalize_document
from src.shared.utils.rapidfuzz_biller import RapidFuzzBiller
from src.shared.utils.text_normalizer import (
    normalize_company_name,
    normalize_name,
    normalize_nit,
    normalize_text_key,
    normalize_upper_spaces,
)
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_cup_repo import FakeCupRepo
from tests.fakes.fake_imedical_repo import FakeImedicalRepo
from tests.fakes.fake_nit_scraper import FakeNitScraper
from tests.fakes.fake_rates_repo import FakeRatesRepo
from tests.fakes.fake_billing_redirect_repo import FakeBillingRedirectRepo
from tests.fakes.fake_tian_repo import FakeTianRepo
from tests.golden._odoo_simulado import OdooSimulado, ServerProxySimulado

RAIZ = Path(__file__).resolve().parent
ENTRADAS = RAIZ / "entradas"
ESPERADO = RAIZ / "esperado"

# N1 — Reloj fijo. Fin del mes anterior = 2026-10-31.
FECHA_EJECUCION = datetime(2026, 11, 5, 10, 30, 0)
MARCADOR_TMP = "<TMP>"

# Variables de entorno que el sistema lee; se borran todas y se fijan por escenario
# (N5). Nunca se leen sus valores reales.
_PREFIJOS_ENTORNO = (
    "ODOO_", "DIRECTORY", "TIAN_NIT", "BOOK_", "DAY_", "COMPANY_NAME_MATCH_THRESHOLD",
    "LOCAL_NAME_LOOKUP", "RUES_",
)
_ODOO_SIMULADO = {
    "ODOO_URL": "http://odoo.simulado", "ODOO_DB": "simulada",
    "ODOO_USERNAME": "golden", "ODOO_API_KEY": "no-es-una-clave",
}


# ── Reloj ────────────────────────────────────────────────────────────────────
class _RelojDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FECHA_EJECUCION if tz is None else FECHA_EJECUCION.replace(tzinfo=tz)


class _RelojDate(date):
    @classmethod
    def today(cls):
        return FECHA_EJECUCION.date()


def _reloj():
    return FECHA_EJECUCION


def fijar_reloj(mp):
    mp.setattr("src.odooInjection.config.date", _RelojDate)
    mp.setattr("src.odooInjection.application.use_cases.inject_invoices_to_odoo.datetime", _RelojDatetime)
    mp.setattr("src.scrapping.infrastructure.reporting.not_found_companies_log_generator.datetime", _RelojDatetime)
    mp.setattr("src.dataProcessing.infrastructure.reporting.cup_novelties_log_generator.datetime", _RelojDatetime)
    mp.setattr(main, "datetime", _RelojDatetime)

    # _normalize_fecha hace `from datetime import date` dentro de la función: solo
    # durante esa llamada se expone un módulo `datetime` cuyo `date.today()` es fijo.
    original = AssignRatesFromExcel._normalize_fecha

    def _normalize_fecha_con_reloj(self, df):
        real = sys.modules["datetime"]
        sombra = types.ModuleType("datetime")
        sombra.__dict__.update(real.__dict__)
        sombra.date = _RelojDate
        sys.modules["datetime"] = sombra
        try:
            return original(self, df)
        finally:
            sys.modules["datetime"] = real

    mp.setattr(AssignRatesFromExcel, "_normalize_fecha", _normalize_fecha_con_reloj)


def entorno_controlado(mp, **valores):
    for clave in list(os.environ):
        if clave.startswith(_PREFIJOS_ENTORNO):
            mp.delenv(clave, raising=False)
    for clave, valor in valores.items():
        if valor is not None:
            mp.setenv(clave, str(valor))


# ── Dobles ───────────────────────────────────────────────────────────────────
class LoggerGrabador:
    """Registra solo los mensajes al usuario (`user_msg`): son el contrato visible.
    Los mensajes técnicos (logs.log) no se comparan: cambian legítimamente al optimizar."""

    def __init__(self):
        self.mensajes_usuario: list[dict] = []

    def _r(self, nivel, user_msg):
        if user_msg:
            self.mensajes_usuario.append({"nivel": nivel, "mensaje": str(user_msg)})

    def debug(self, message, *, user_msg=None):
        self._r("DEBUG", user_msg)

    def info(self, message, *, user_msg=None):
        self._r("INFO", user_msg)

    def warning(self, message, *, user_msg=None):
        self._r("WARNING", user_msg)

    def error(self, message, exc_info=None, *, user_msg=None):
        self._r("ERROR", user_msg)

    def critical(self, message, exc_info=None, *, user_msg=None):
        self._r("CRITICAL", user_msg)


class CatalogoEnMemoria:
    """Tabla con `name` único (cities, packages, providers, specials, billers)."""

    def __init__(self, filas=None):
        self._data = [dict(f) for f in filas or []]
        self._next_id = max((f["id"] for f in self._data), default=0) + 1

    def all(self):
        return [dict(f) for f in self._data]

    def find_by_name(self, name):
        fila = next((f for f in self._data if f["name"] == name), None)
        return (fila["id"], fila["name"]) if fila else None

    def save(self, entidad):
        existente = self.find_by_name(entidad.name)
        if existente:
            return existente
        self._data.append({"id": self._next_id, "name": entidad.name})
        self._next_id += 1
        return self._next_id - 1, entidad.name

    def save_batch(self, entidades):
        return [self.save(e) for e in entidades]

    def update(self, entidad):
        fila = next((f for f in self._data if f["id"] == entidad.id), None)
        if fila is None:
            return False
        fila["name"] = entidad.name
        return True


class _SesionNula:
    def close(self):
        pass


def _rates_repo(filas):
    repo = FakeRatesRepo()
    for r in filas:
        repo._data[(r["rateable_id"], r["city_id"], r["cup_id"], r["activity_id"], r["rateable_type"])] = r["rate"]
    return repo


def _company_repo(bd):
    repo = FakeCompanyRepo([dict(c) for c in bd.get("companies", [])])
    repo._packages = [dict(p) for p in bd.get("companies_packages", [])]
    return repo


def _biller_company_repo(bd):
    repo = FakeBillerCompanyRepo()
    repo._data = [dict(x) for x in bd.get("biller_companies", [])]
    return repo


def _scraper(rues: dict) -> FakeNitScraper:
    def _nr(d):
        return NitResult(**d)
    return FakeNitScraper(
        by_nit={k: _nr(v) for k, v in rues["por_nit"].items()},
        by_name={k: _nr(v) for k, v in rues["por_nombre"].items()},
        omit=rues["sin_respuesta"],
    )


def _constante(valor):
    return lambda *a, **k: valor


def _odoo(mp, ruta_json: Path) -> OdooSimulado:
    odoo = OdooSimulado(_leer_json(ruta_json))
    mp.setattr(xmlrpc.client, "ServerProxy", ServerProxySimulado(odoo))
    return odoo


def _consola_grabadora() -> Console:
    return Console(record=True, width=120, file=io.StringIO(), color_system=None)


# ── Serialización ────────────────────────────────────────────────────────────
def _leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _valor_celda(v):
    if isinstance(v, datetime):
        return f"datetime:{v.isoformat()}"
    if isinstance(v, date):
        return f"date:{v.isoformat()}"
    return v


def leer_xlsx(ruta: Path) -> dict:
    """N3 — Libro → JSON canónico: hojas en orden, valores, relleno, formato numérico,
    negrita, paneles inmovilizados y celdas combinadas. Se ignoran los metadatos del
    archivo (fechas de creación del zip/docProps), anchos de columna, bordes y estilos de tabla."""
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hojas = []
    for ws in wb.worksheets:
        filas, estilos = [], {}
        for row in ws.iter_rows():
            valores = [_valor_celda(c.value) for c in row]
            while valores and valores[-1] is None:
                valores.pop()
            filas.append(valores)
            for c in row:
                e = {}
                fill = c.fill
                if fill is not None and fill.fill_type == "solid":
                    rgb = getattr(fill.fgColor, "rgb", None)
                    if isinstance(rgb, str):
                        e["relleno"] = rgb[-6:].upper()
                if c.number_format and c.number_format != "General":
                    e["formato"] = c.number_format
                if c.font is not None and c.font.b:
                    e["negrita"] = True
                if e:
                    estilos[c.coordinate] = e
        while filas and not filas[-1]:
            filas.pop()
        hoja = {"nombre": ws.title, "filas": filas}
        if estilos:
            hoja["estilos"] = estilos
        if ws.freeze_panes:
            hoja["inmovilizar"] = ws.freeze_panes
        if ws.merged_cells.ranges:
            hoja["combinadas"] = sorted(str(r) for r in ws.merged_cells.ranges)
        hojas.append(hoja)
    wb.close()
    return {"hojas": hojas}


def _leer_archivo(ruta: Path):
    if ruta.suffix.lower() == ".xlsx":
        return leer_xlsx(ruta)
    if ruta.suffix.lower() == ".json":
        return _leer_json(ruta)
    return ruta.read_text(encoding="utf-8")


def _hash(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def copiar_entradas(origen: Path, destino: Path, nombres=None) -> dict[str, str]:
    """Copia entradas al directorio de trabajo; devuelve {ruta relativa: hash} para
    luego excluir de la instantánea los archivos que el sistema no modificó."""
    copiados = {}
    for p in sorted(origen.rglob("*")):
        rel = p.relative_to(origen)
        if p.is_dir() or (nombres is not None and rel.parts[0] not in nombres):
            continue
        objetivo = destino / rel
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, objetivo)
        copiados[rel.as_posix()] = _hash(objetivo)
    return copiados


def instantanea_archivos(trabajo: Path, sin_cambios: dict[str, str]) -> dict:
    salida = {}
    for p in sorted(trabajo.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(trabajo).as_posix()
        if sin_cambios.get(rel) == _hash(p):
            continue  # entrada copiada que el sistema no tocó
        salida[rel] = _leer_archivo(p)
    return salida


def normalizar(obj, trabajo: Path):
    """N2 — Rutas absolutas del directorio temporal → <TMP>."""
    rutas = sorted({str(trabajo), str(trabajo.resolve())}, key=len, reverse=True)

    def _n(x):
        if isinstance(x, str):
            for r in rutas:
                x = x.replace(r, MARCADOR_TMP)
            return x
        if isinstance(x, dict):
            return {_n(k): _n(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [_n(v) for v in x]
        return x

    return _n(obj)


# ── Escenarios ───────────────────────────────────────────────────────────────
def esc_normalizadores(entradas: Path, trabajo: Path, mp) -> dict:
    casos = _leer_json(entradas / "casos.json")
    logger = LoggerGrabador()
    fuzz = RapidFuzzBiller(logger)
    resolver = CityAccountResolver()

    def _doc(v):
        r = normalize_document(v)
        return {k: getattr(r, k) for k in r.__dataclass_fields__}

    return {
        "normalize_nit": [[v, normalize_nit(v)] for v in casos["nits"]],
        "normalize_document": [[v, _doc(v)] for v in casos["documentos"]],
        "valor_opcion3": [[v, _is_success(v)] for v in casos["valores_opcion3"]],
        "fuzz_property": [
            [c, fuzz.fuzz_property(c["nombre"], [{"name": n} for n in c["catalogo"]], threshold=c["umbral"])]
            for c in casos["fuzzy"]
        ],
        "cuenta_analitica": [[c, list(resolver.resolve(c))] for c in casos["ciudades_cuenta_analitica"]],
        "claves_texto": [
            [t, {"normalize_name": normalize_name(t), "normalize_text_key": normalize_text_key(t),
                 "normalize_company_name": normalize_company_name(t),
                 "normalize_upper_spaces": normalize_upper_spaces(t)}]
            for t in casos["claves_texto"]
        ],
        "mensajes_usuario": logger.mensajes_usuario,
    }


def esc_opcion1(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"libro_nits.xlsx"})
    entorno_controlado(mp, DIRECTORY=trabajo, BOOK_ROUTE=trabajo, BOOK_NAME="libro_nits.xlsx", **_ODOO_SIMULADO)
    bd = _leer_json(entradas / "bd.json")
    company_repo = _company_repo(bd)
    _odoo(mp, entradas / "odoo.json")
    consola = _consola_grabadora()
    mp.setattr(ctrl_opcion1, "RuesPlaywrightScraper", _constante(_scraper(_leer_json(entradas / "rues.json"))))
    mp.setattr(ctrl_opcion1, "SaCompanyRepository", _constante(company_repo))
    mp.setattr(ctrl_opcion1, "get_session", _constante(_SesionNula()))
    mp.setattr(ctrl_opcion1, "XlsxFindingsWriter", lambda base: XlsxFindingsWriter(base, clock=_reloj))
    mp.setattr(ctrl_opcion1, "console", consola)
    logger = LoggerGrabador()

    ctrl_opcion1.execute_web_scrapping(logger)

    return {
        "archivos": instantanea_archivos(trabajo, copiados),
        "bd_companies": sorted(({"nit": c["nit"], "name": c["name"]} for c in company_repo.all()),
                               key=lambda c: c["nit"]),
        "consola": consola.export_text(),
        "mensajes_usuario": logger.mensajes_usuario,
    }


def esc_opcion2(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"facturadores.xlsx", "data.json"})
    entorno_controlado(mp, DIRECTORY=trabajo, **_ODOO_SIMULADO)
    bd = _leer_json(entradas / "bd.json")
    billers = CatalogoEnMemoria(bd["billers"])
    company_repo = _company_repo(bd)
    links = _biller_company_repo(bd)
    _odoo(mp, entradas / "odoo.json")
    mp.setattr(nit_service, "RuesPlaywrightScraper", _constante(_scraper(_leer_json(entradas / "rues.json"))))
    mp.setattr(ctrl_opcion2, "ask_excel_path", _constante(trabajo / "facturadores.xlsx"))
    mp.setattr(ctrl_opcion2, "ask_sheet_name", _constante("Hoja1"))
    mp.setattr(ctrl_opcion2, "get_session", _constante(_SesionNula()))
    mp.setattr(ctrl_opcion2, "SaBillerRepository", _constante(billers))
    mp.setattr(ctrl_opcion2, "SaCompanyRepository", _constante(company_repo))
    mp.setattr(ctrl_opcion2, "SaBillerCompanyRepository", _constante(links))
    mp.setattr(ctrl_opcion2, "XlsxFindingsWriter", lambda base: XlsxFindingsWriter(base, clock=_reloj))
    logger = LoggerGrabador()

    ctrl_opcion2.import_billers(logger)

    # N4 — ids sustitutos → nombres (ver README).
    biller_name = {b["id"]: b["name"] for b in billers.all()}
    company_nit = {c["id"]: c["nit"] for c in company_repo.all()}
    return {
        "archivos": instantanea_archivos(trabajo, copiados),
        "bd_billers": sorted(b["name"] for b in billers.all()),
        "bd_companies": sorted(({"nit": c["nit"], "name": c["name"]} for c in company_repo.all()),
                               key=lambda c: c["nit"]),
        "bd_companies_billers": sorted(
            ({"nit": company_nit.get(x["company"]), "facturador": biller_name.get(x["biller"])} for x in links.all()),
            key=lambda x: (str(x["nit"]), str(x["facturador"])),
        ),
        "mensajes_usuario": logger.mensajes_usuario,
    }


def esc_opcion3(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"tarifario_crudo.xlsx"})
    entorno_controlado(mp)
    bd = _leer_json(entradas / "bd.json")
    salida = trabajo / "salida"
    salida.mkdir()
    mp.setattr(ctrl_opcion3, "ask_excel_path", _constante(trabajo / "tarifario_crudo.xlsx"))
    mp.setattr(ctrl_opcion3, "ask_directory_path", _constante(salida))
    mp.setattr(ctrl_opcion3, "get_session", _constante(_SesionNula()))
    mp.setattr(ctrl_opcion3, "SaCupRepository", lambda *_: FakeCupRepo(bd["cups"]))
    logger = LoggerGrabador()

    ctrl_opcion3.import_information(logger)

    return {"archivos": instantanea_archivos(trabajo, copiados), "mensajes_usuario": logger.mensajes_usuario}


def _estado_tarifas(catalogos: dict, rates_repo) -> list[dict]:
    """N4 — Tarifas expresadas por nombres, no por ids sustitutos."""
    nombres = {tipo: {f["id"]: f["name"] for f in repo.all()} for tipo, repo in catalogos.items()}
    filas = []
    for (rid, cid, cup_id, aid, tipo), valor in rates_repo._data.items():
        filas.append({
            "tipo": tipo, "contrato": nombres[tipo].get(rid), "ciudad": nombres["City"].get(cid),
            "cup_id": cup_id, "actividad_id": aid, "tarifa": valor,
        })
    return sorted(filas, key=lambda f: json.dumps(f, sort_keys=True, ensure_ascii=False))


def esc_opcion4(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"tarifario_normalizado.xlsx", "tarifario_ciudad_nula.xlsx"})
    entorno_controlado(mp)
    bd = _leer_json(entradas / "bd.json")
    catalogos = {
        "Package": CatalogoEnMemoria(bd["packages"]), "Provider": CatalogoEnMemoria(bd["providers"]),
        "Special": CatalogoEnMemoria(bd["specials"]), "City": CatalogoEnMemoria(bd["cities"]),
    }
    rates = _rates_repo(bd["rates"])
    libro = iter(["tarifario_normalizado.xlsx", "tarifario_ciudad_nula.xlsx"])
    mp.setattr(ctrl_opcion4, "ask_excel_path", lambda *_: trabajo / next(libro))
    mp.setattr(ctrl_opcion4, "get_session", _constante(_SesionNula()))
    mp.setattr(ctrl_opcion4, "SaPackageRepository", _constante(catalogos["Package"]))
    mp.setattr(ctrl_opcion4, "SaProviderRepository", _constante(catalogos["Provider"]))
    mp.setattr(ctrl_opcion4, "SaSpecialRepository", _constante(catalogos["Special"]))
    mp.setattr(ctrl_opcion4, "SaCityRepository", _constante(catalogos["City"]))
    mp.setattr(ctrl_opcion4, "SaActivityRepository", _constante(CatalogoEnMemoria(bd["activities"])))
    mp.setattr(ctrl_opcion4, "SaCupRepository", _constante(FakeCupRepo(bd["cups"])))
    mp.setattr(ctrl_opcion4, "SaRatesRepository", _constante(rates))
    mp.setattr(ctrl_opcion4, "XlsxFindingsWriter", lambda base: XlsxFindingsWriter(base, clock=_reloj))
    logger = LoggerGrabador()

    ctrl_opcion4.import_rates(logger)
    resultado = {
        "archivos": instantanea_archivos(trabajo, copiados),
        "bd_catalogos": {tipo: sorted(f["name"] for f in repo.all()) for tipo, repo in catalogos.items()},
        "bd_rates": _estado_tarifas(catalogos, rates),
        "mensajes_usuario": logger.mensajes_usuario,
    }

    # Segunda corrida, sobre el estado anterior: libro con CIUDAD vacía.
    logger = LoggerGrabador()
    excepcion = _capturar(lambda: ctrl_opcion4.import_rates(logger))
    resultado["ciudad_nula"] = {
        "excepcion": excepcion,
        "bd_rates_sin_cambios": _estado_tarifas(catalogos, rates) == resultado["bd_rates"],
        "mensajes_usuario": logger.mensajes_usuario,
    }
    return resultado


def _capturar(fn) -> str | None:
    """Ejecuta `fn`; si lanza, devuelve 'Tipo: mensaje' (el comportamiento actual es parte del golden)."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    return None


def esc_opcion6(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"atenciones.xlsx", "facturas.xlsx", "data.json"})
    entorno_controlado(mp, DIRECTORY=trabajo, TIAN_NIT="860000001", **_ODOO_SIMULADO)
    bd = _leer_json(entradas / "bd.json")
    imedical = FakeImedicalRepo(bd["imedical"])
    _odoo(mp, entradas / "odoo.json")
    consola = _consola_grabadora()
    libros = iter([trabajo / "atenciones.xlsx", trabajo / "facturas.xlsx"])
    hojas = iter(["Atenciones", "Facturas"])
    reemplazos = {
        "ask_excel_path": lambda *_: next(libros),
        "ask_sheet_name": lambda *_: next(hojas),
        "get_session": _constante(_SesionNula()),
        "SaBillerRepository": _constante(CatalogoEnMemoria(bd["billers"])),
        "SaCompanyRepository": _constante(_company_repo(bd)),
        "SaBillerCompanyRepository": _constante(_biller_company_repo(bd)),
        "SaPackageRepository": _constante(CatalogoEnMemoria(bd["packages"])),
        "SaProviderRepository": _constante(CatalogoEnMemoria(bd["providers"])),
        "SaSpecialRepository": _constante(CatalogoEnMemoria(bd["specials"])),
        "SaCityRepository": _constante(CatalogoEnMemoria(bd["cities"])),
        "SaActivityRepository": _constante(CatalogoEnMemoria(bd["activities"])),
        "SaRatesRepository": _constante(_rates_repo(bd["rates"])),
        "SaCupRepository": _constante(FakeCupRepo(bd["cups"])),
        "SaImedicalRepository": _constante(imedical),
        "SaTianRepository": _constante(FakeTianRepo(bd["tian"])),
        "SaBillingRedirectRepository": _constante(FakeBillingRedirectRepo(bd.get("billing_redirects", []))),
        "XlsxPhaseFindingsReporter": lambda: XlsxPhaseFindingsReporter(clock=_reloj),
        "AssignRatesFromExcel": lambda **k: AssignRatesFromExcel(**k, today=_RelojDate.today),
        "Console": _constante(consola),
    }
    for nombre, valor in reemplazos.items():
        mp.setattr(ctrl_opcion6, nombre, valor)
    logger = LoggerGrabador()

    ctrl_opcion6.assign_rates(logger, with_invoices=True)

    return {
        "archivos": instantanea_archivos(trabajo, copiados),
        "bd_imedical_guardados": [[vars(c) for c in lote] for lote in imedical.saved_batches],
        "consola": consola.export_text(),
        "mensajes_usuario": logger.mensajes_usuario,
    }


def esc_opcion7(entradas: Path, trabajo: Path, mp) -> dict:
    copiados = copiar_entradas(entradas, trabajo, {"CONSOLIDADO.xlsx"})
    entorno_controlado(mp)
    bd = _leer_json(entradas / "bd.json")
    mp.setattr(ctrl_opcion7, "get_session", _constante(_SesionNula()))
    mp.setattr(ctrl_opcion7, "SaCupRepository", lambda *_: FakeCupRepo(bd["cups"]))
    logger = LoggerGrabador()

    ctrl_opcion7.generate_pre_invoices(logger)

    return {"archivos": instantanea_archivos(trabajo, copiados), "mensajes_usuario": logger.mensajes_usuario}


def esc_opcion8(entradas: Path, trabajo: Path, mp) -> dict:
    """La opción 8 está desconectada del menú; se ejecuta su controller directamente.
    Se corre dos veces seguidas para fijar el comportamiento del anti-duplicados."""
    copiados = copiar_entradas(entradas, trabajo, {"pre-facturas", "odoo-output"})
    entorno_controlado(mp, ODOO_PRODUCTOS_GRAVADOS="890202, 903810-01", **_ODOO_SIMULADO)  # [AUD-63]
    odoo = _odoo(mp, entradas / "odoo.json")
    corridas = []
    for _ in range(2):
        logger = LoggerGrabador()
        antes = len(odoo.creados)
        ctrl_opcion8.inject_invoices(logger)
        corridas.append({
            "facturas_creadas": odoo.creados[antes:],
            "log_inyeccion": leer_xlsx(trabajo / "odoo-output" / "log_inyeccion.xlsx"),
            "mensajes_usuario": logger.mensajes_usuario,
        })
    archivos = instantanea_archivos(trabajo, copiados)
    archivos.pop("odoo-output/log_inyeccion.xlsx", None)  # ya está por corrida
    return {"corridas": corridas, "archivos": archivos}


def esc_menu(entradas: Path, trabajo: Path, mp) -> dict:
    casos = _leer_json(entradas / "casos.json")
    llamadas = []
    mp.setattr(main, "assign_rates", lambda logger, with_invoices=False: llamadas.append(with_invoices))
    mp.setattr(main, "console", _consola_grabadora())

    def _con_dia(dia):
        class _Dia(_RelojDatetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, dia, 10, 30)  # octubre: tiene día 31
        return _Dia

    salida = {"ventana": casos["ventana"], "pide_libro_facturas": [], "configuraciones_invalidas": []}
    entorno_controlado(mp, **casos["ventana"])
    for dia in casos["dias"]:
        llamadas.clear()
        mp.setattr(main, "datetime", _con_dia(dia))
        main.dispatch_option("6", LoggerGrabador())
        salida["pide_libro_facturas"].append([dia, llamadas[0]])
    for config in casos["configuraciones_invalidas"]:
        entorno_controlado(mp, **config)
        logger = LoggerGrabador()
        llamadas.clear()
        sigue = main.safe_dispatch("6", logger)
        salida["configuraciones_invalidas"].append({
            "config": config, "menu_continua": sigue, "llamo_asignar": bool(llamadas),
            "mensajes_usuario": logger.mensajes_usuario,
        })
    return salida


ESCENARIOS = {
    "normalizadores": esc_normalizadores,
    "opcion1_web_scrapping": esc_opcion1,
    "opcion2_facturadores": esc_opcion2,
    "opcion3_tratamiento": esc_opcion3,
    "opcion4_tarifas": esc_opcion4,
    "opcion6_asignar": esc_opcion6,
    "opcion7_prefacturas": esc_opcion7,
    "opcion8_inyeccion": esc_opcion8,
    "menu_ventana_dias": esc_menu,
}


# ── N6: orden no determinista del sistema actual ────────────────────────────
# Solo donde se comprobó que el orden cambia entre procesos (PYTHONHASHSEED distinto)
# porque el código agrupa sin `maintain_order`. Ver README y docs/auditoria.md AUD-80/81.
def _celda_a_fila(coord: str) -> tuple[str, int]:
    letras = "".join(ch for ch in coord if ch.isalpha())
    return letras, int(coord[len(letras):])


def _reordenar_filas(hoja: dict, indices: list[int], clave) -> None:
    filas = hoja["filas"]
    ordenados = sorted(indices, key=lambda i: clave(filas[i]))
    nuevas, mapa = list(filas), {}
    for destino, origen in zip(indices, ordenados):
        nuevas[destino] = filas[origen]
        mapa[origen + 1] = destino + 1  # filas de Excel (1-based)
    hoja["filas"] = nuevas
    if "estilos" in hoja:
        estilos = {}
        for coord, estilo in hoja["estilos"].items():
            col, fila = _celda_a_fila(coord)
            estilos[f"{col}{mapa.get(fila, fila)}"] = estilo
        hoja["estilos"] = dict(sorted(estilos.items(), key=lambda kv: (_celda_a_fila(kv[0])[1], kv[0])))


def _lista_ordenada(valor):
    return ", ".join(sorted(valor.split(", "))) if isinstance(valor, str) else valor


def _ordenar_novedades_cups(libro: dict) -> None:
    """cup_column_validator.py:100-102 y 125-127: `group_by` sin maintain_order y
    `CONTRATO.unique()` → orden de novedades y de 'Contratos (ejemplos)' arbitrario."""
    for hoja in libro["hojas"]:
        filas = hoja["filas"]
        if not filas or "Contratos (ejemplos)" not in filas[0]:
            continue
        col = filas[0].index("Contratos (ejemplos)")
        datos = [i for i, f in enumerate(filas[1:], start=1) if f and isinstance(f[0], int)]
        for i in datos:
            filas[i] = list(filas[i])
            filas[i][col] = _lista_ordenada(filas[i][col])
        _reordenar_filas(hoja, datos, lambda f: json.dumps(f[1:], ensure_ascii=False, default=str))
        for numero, i in enumerate(datos, start=1):
            hoja["filas"][i][0] = numero


def _ordenar_facturas(libro: dict) -> None:
    """assigned_rates.py:57-71: `unique()` + `group_by` sin maintain_order antes de
    `str.join(", ")` → el orden de los números en FACTURAS es arbitrario."""
    for hoja in libro["hojas"]:
        for n_encabezado, encabezado in enumerate(hoja["filas"][:2]):
            if "FACTURAS" in encabezado:
                col = encabezado.index("FACTURAS")
                for fila in hoja["filas"][n_encabezado + 1:]:
                    if len(fila) > col:
                        fila[col] = _lista_ordenada(fila[col])
                break


def _orden_no_determinista(nombre: str, instantanea: dict) -> dict:
    archivos = instantanea.get("archivos", {})
    if nombre == "opcion3_tratamiento" and "logs/novedades_cups.xlsx" in archivos:
        _ordenar_novedades_cups(archivos["logs/novedades_cups.xlsx"])
    if nombre == "opcion6_asignar":
        for ruta, contenido in archivos.items():
            if ruta.endswith(".xlsx"):
                _ordenar_facturas(contenido)
    return instantanea


def ejecutar(nombre: str, trabajo: Path, mp) -> dict:
    """Ejecuta un escenario en `trabajo` (directorio vacío) y devuelve la instantánea normalizada."""
    trabajo.mkdir(parents=True, exist_ok=True)
    mp.chdir(trabajo)
    fijar_reloj(mp)
    instantanea = ESCENARIOS[nombre](ENTRADAS / nombre, trabajo, mp)
    return normalizar(_orden_no_determinista(nombre, instantanea), trabajo)


def serializar(instantanea: dict) -> str:
    return json.dumps(instantanea, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
