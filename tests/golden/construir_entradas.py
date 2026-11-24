"""Construye las entradas fijas del golden master en tests/golden/entradas/.

Se ejecuta UNA vez (o cuando se agregue un caso). Las entradas generadas se
versionan: el golden compara contra ellas, no contra este script.

    python tests/golden/construir_entradas.py           # falla si ya existen
    python tests/golden/construir_entradas.py --forzar  # las reconstruye

Cada caso indica entre corchetes el hallazgo o la regla de docs/auditoria.md que cubre.
Ningún dato es real: NITs, nombres y precios son inventados.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import PatternFill

RAIZ = Path(__file__).resolve().parent / "entradas"

CUPS = [
    {"id": 1, "code": "890201", "name": "CONSULTA MEDICINA GENERAL"},
    {"id": 2, "code": "890202", "name": "CONSULTA ESPECIALISTA"},
    {"id": 3, "code": "903810", "name": "COLESTEROL TOTAL"},
    {"id": 4, "code": "903810-01", "name": "COLESTEROL TOTAL SUERO"},
    {"id": 5, "code": "871121", "name": "RX TORAX"},
    {"id": 6, "code": "990101", "name": "EXAMEN SIN TARIFA"},
]
ACTIVIDADES = [{"id": 1, "name": "INTRA"}, {"id": 2, "name": "EXTRA"}]
TARIFA_COLS = ["CONTRATO", "CIUDAD", "CUP", "EXAMEN", "INTRA O EXTRA", "VALOR"]

# Columnas fijas del libro de atenciones (entrada de la opción 6)
ATENCION_COLS = [
    "Base", "Ingreso N°", "Sede", "Ciudad", "NIT", "Empresa", "Empresa Misión",
    "Medio de Pago", "Fecha Ingreso", "Tipo Examen", "Cargo", "Paciente",
    "N° Identificación", "Número de Póliza", "ORDEN, CENTRO DE COSTO, CECO, PET",
    "ORDEN, CENTRO DE COSTO, CECO, PET_1", "TIPO DE ACTIVIDAD", "Observaciones Ingreso",
]
CUP_COLS = ["890201", "890202", "903810-01", "871121", "990101"]

# Orden de columnas fijas del CONSOLIDADO (assigned_rates._FIXED_COLUMNS_ORDER)
CONSOLIDADO_COLS = [
    "Base", "Ingreso N°", "Sede", "Ciudad", "NIT", "FACTURADOR", "Especial / General",
    "PAQUETE", "Empresa", "Empresa Misión", "Medio de Pago", "Fecha Ingreso", "Tipo Examen",
    "Cargo", "Paciente", "N° Identificación", "Número de Póliza",
    "ORDEN, CENTRO DE COSTO, CECO, PET", "ORDEN, CENTRO DE COSTO, CECO, PET_1", "FACTURAS",
    "TIPO DE ACTIVIDAD", "Observaciones Ingreso", "Total",
]
# Orden de columnas fijas de la pre-factura (split_by_nit.FIXED_COLUMNS)
PREFACTURA_COLS = [
    "Base", "Ingreso N°", "Sede", "Ciudad", "FACTURADOR", "Especial / General", "PAQUETE",
    "NIT", "Empresa", "Empresa Misión", "Medio de Pago", "Fecha Ingreso", "Tipo Examen",
    "Cargo", "Paciente", "N° Identificación", "Número de Póliza", "FACTURAS",
    "ORDEN, CENTRO DE COSTO, CECO, PET", "ORDEN, CENTRO DE COSTO, CECO, PET_1",
    "TIPO DE ACTIVIDAD", "Observaciones Ingreso", "Total",
]


def _libro(ruta: Path, hojas: dict[str, list[list]], rellenos: dict | None = None):
    """Escribe un .xlsx con openpyxl. `rellenos` = {hoja: {(fila, col): "RRGGBB"}} (1-based)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(nombre)
        for fila in filas:
            ws.append(fila)
        for (f, c), color in (rellenos or {}).get(nombre, {}).items():
            ws.cell(row=f, column=c).fill = PatternFill("solid", fgColor=color)
    # Metadatos fijos: el contenido no depende del momento de construcción.
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)


def _json(ruta: Path, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _partner(pid, name, ref_num=False, vat=False, special=False, base=False):
    return {"id": pid, "name": name, "ref_num": ref_num, "vat": vat,
            "rate_base_special_id": special, "rate_base_id": base}


# ─────────────────────────────────────────────────────────────────────────────
def normalizadores():
    d = RAIZ / "normalizadores"
    _json(d / "casos.json", {
        "nits": ["900123456", "900.123.456-7", "9001234567", "1012345678", "80012345-6",
                 "12345", "", "None", " 900 123 456 ", "NIT 900123456"],          # [AUD-28, P-09]
        "fuzzy": [                                                                   # [AUD-03]
            {"nombre": "ACME", "catalogo": ["ACME INDUSTRIAL S.A.S.", "OTRA"], "umbral": 90},
            {"nombre": "CLINICA SAN JOSE", "catalogo": ["CLINICA SAN JOSE DE CUCUTA SA"], "umbral": 90},
            {"nombre": "ESPECIAL ADECCO 2", "catalogo": ["ESPECIAL ADECCO"], "umbral": 95},
            {"nombre": "PAQUETE A-2025", "catalogo": ["PAQUETE A 2025"], "umbral": 95},
            {"nombre": "BOGOTA D.C", "catalogo": ["BOGOTA", "MEDELLIN"], "umbral": 95},
            {"nombre": "XYZ", "catalogo": [], "umbral": 90},
        ],
        "claves_texto": ["Clínica San José", "EMPRESA ALFA S.A.S.", "  Bogotá, D.C. ", "Ñandú & Cía"],
    })


# ─────────────────────────────────────────────────────────────────────────────
def opcion1():
    d = RAIZ / "opcion1_web_scrapping"
    _libro(d / "libro_nits.xlsx", {"nits": [
        ["nits", "empresa"],
        ["900111111", "EMPRESA ALFA SAS"],        # Odoo por NIT
        ["900.111.111-7", "EMPRESA ALFA"],        # NIT con DV y puntos → normaliza
        [None, "SIN NIT SAS"],                    # [AUD-72] celda de NIT vacía (con empresa)
        ["830050228", "GRUPO ADECCO"],            # BD local con otro nombre; Odoo lo corrige
        ["912345678", "EMPRESA RUES SAS"],        # solo RUES
        ["555555555", "ACME"],                    # [AUD-03] nombre corto ⊂ partner de Odoo
        ["444444444", "FALLA RUES SAS"],          # [AUD-06] RUES no devuelve resultado (fallo técnico)
        ["1012345678", "PERSONA NATURAL"],        # [P-09] cédula de 10 dígitos
        ["333333333", "SOLO BD LOCAL"],           # [AUD-14] solo en BD local
    ]})
    _json(d / "bd.json", {"companies": [
        {"id": 1, "nit": "830050228", "name": "GRUPO ADECCO SA"},
        {"id": 2, "nit": "333333333", "name": "SOLO BD LOCAL"},
    ]})
    _json(d / "odoo.json", {"res.partner": [
        _partner(10, "EMPRESA ALFA S.A.S.", ref_num="900111111"),
        _partner(11, "GRUPO ADECCO S.A.", ref_num="830050228"),
        _partner(14, "ACME INDUSTRIAL S.A.S.", ref_num="777888999"),
    ]})
    _json(d / "rues.json", {
        "por_nit": {"912345678": {"nit": 912345678, "is_company": True, "name": "EMPRESA RUES SAS"}},
        "por_nombre": {},
        "sin_respuesta": ["444444444"],
    })


# ─────────────────────────────────────────────────────────────────────────────
def opcion2():
    d = RAIZ / "opcion2_facturadores"
    _libro(d / "facturadores.xlsx", {"Hoja1": [
        ["GESTOR", "NIT", "EMPRESA"],
        ["ALFA", "900111111", "EMPRESA ALFA SAS"],
        ["Alfa S.A.S.", "830050228", "GRUPO ADECCO"],         # gestor por fuzzy
        ["BETA", "1012345678", "PERSONA NATURAL"],            # [AUD-26] cédula truncada
        ["BETA", "555555555", "EMPRESA FANTASMA"],            # [AUD-27] no verificada, igual se guarda
        ["GAMMA", "900111111", "EMPRESA ALFA SAS"],           # vínculo duplicado: última fila gana
    ]})
    _json(d / "bd.json", {
        "billers": [{"id": 1, "name": "ALFA"}],
        "companies": [{"id": 1, "nit": "830050228", "name": "GRUPO ADECCO SA"}],
    })
    _json(d / "odoo.json", {"res.partner": [_partner(10, "EMPRESA ALFA S.A.S.", ref_num="900111111")]})
    _json(d / "rues.json", {"por_nit": {}, "por_nombre": {}, "sin_respuesta": []})
    _json(d / "data.json", [])


# ─────────────────────────────────────────────────────────────────────────────
def _atencion(base, ingreso, ciudad, nit, empresa, fecha, paciente, ident, actividad, cups, sede="SEDE NORTE"):
    fila = [base, ingreso, sede, ciudad, nit, empresa, "Mision S.A.S.", "Crédito", fecha,
            "Ingreso", "Auxiliar (a) - Bodega", paciente, ident, None, "OC-1", None, actividad, None]
    return fila + [cups.get(c) for c in CUP_COLS]


def opcion6():
    d = RAIZ / "opcion6_asignar"
    filas = [
        ATENCION_COLS + CUP_COLS,
        # Odoo especial (31100.7 truncado) + 890202: línea Odoo con precio 0 → fase 1 local
        _atencion("OCTUBRE 1-20", "1", "BOGOTA", "900111111", "Empresa Alfa S A S", "2026-10-05",
                  "Ana Pérez", "CC 1001", "INTRAMURAL", {"890201": 1, "890202": 1}),
        # NIT con puntos y DV; EXTRA → base Odoo vencida [odoo_tarifa_vencida]
        _atencion("OCTUBRE 1-20", "2", "Bogotá", "900.111.111-7", "EMPRESA ALFA SAS", "05/10/2026",
                  "Luis Gómez", " cc 1001 ", "EXTRAMURAL", {"871121": 1}),
        # Solo BD local (proveedor sin tarifa) → fase 2; fecha posterior al límite [AUD-48]
        _atencion("OCTUBRE 1-20", "3", "BOGOTA", "800222222-5", "Beta Ltda", "2026-11-03",
                  "Marta Ruiz", "1003", None, {"871121": 1}),
        # Solo RUES (data.json) → paquete por defecto → fase 3 con dos candidatos [AUD-05]
        _atencion("OCTUBRE 1-20", "4", "CALI", "912345678", "Empresa Rues", "2026-10-12",
                  "Pedro Díaz", "1004", "INTRA", {"890201": 1}),
        # CUP con sufijo → fase 4 (CUP base en PAQUETE C 2025); mes 13 → intercambio
        _atencion("OCTUBRE 1-20", "5", "BOGOTA", "900111111", "EMPRESA ALFA SAS", "2026-13-10",
                  "Sara Mora", "1005", "INTRA", {"903810-01": 1}),
        # Odoo sin tarifas → fase 5 (CUP base, otro paquete, misma ciudad); fecha d/m/aaaa sin ceros
        _atencion("OCTUBRE 1-20", "6", "MEDELLIN", "830050228", "Grupo Adecco", "5/1/2026",
                  "Juan Ríos", "1006", "INTRA", {"903810-01": 1}),
        # Fase 6 (cualquier ciudad); celda de fecha real
        _atencion("OCTUBRE 1-20", "7", "MEDELLIN", "830050228", "Grupo Adecco", datetime(2026, 10, 20),
                  "Eva Luna", "1007", "EXTRA", {"871121": 1}),
        # Ciudad inexistente en BD → salta todas las fases locales [AUD-18]
        _atencion("OCTUBRE 1-20", "8", "TUNJA", "830050228", "Grupo Adecco", "2026-10-21",
                  "Iván Cruz", "1008", "EXTRA", {"871121": 1}),
        # i-medical: NIT errado → corregido
        _atencion("IMEDICAL OCTUBRE 1-20", "9", "BOGOTA", "901999999", "Alfa Mal", "2026-10-22",
                  "Rosa Vega", "1009", "INTRA", {"890201": 1}),
        # TIAN: redirección al NIT de TIAN; base Odoo vencida
        _atencion("OCTUBRE 1-20", "10", "BOGOTA", "811000000", "Cliente Tian", "2026-10-23",
                  "Hugo Paz", "1010", "INTRA", {"890201": 1}),
        # NIT inválido, empresa existe en Odoo por nombre (vat con DV)
        _atencion("OCTUBRE 1-20", "11", "CALI", "123", "EMPRESA GAMMA", "2026-10-24",
                  "Lía Sol", "1011", "INTRA", {"890201": 1}),
        # Empresa inexistente → NOVEDAD; CUP sin tarifa → sin_resolver
        _atencion("OCTUBRE 1-20", "12", "CALI", "555555555", "Desconocida XYZ", "2026-10-25",
                  "Noé Gil", "1012", "INTRA", {"990101": 1}),
        # Celda con valor 2 (no se valora, suma en Total) [P-18]; fecha vacía
        _atencion("OCTUBRE 1-20", "13", "BOGOTA", "900111111", "EMPRESA ALFA SAS", None,
                  "Ana Pérez", "CC 1001", "INTRA", {"890201": 2}),
    ]
    _libro(d / "atenciones.xlsx", {"Atenciones": filas})
    _libro(d / "facturas.xlsx", {"Facturas": [
        ["N° Identificación", "# FACTURA"],
        ["CC 1001", "SET100"], ["CC 1001", "SET100"], ["CC 1001", "FAC200"],
        ["1003", "SET300"], ["1004", "FAC400"],
    ]})
    _json(d / "bd.json", {
        "companies": [
            {"id": 1, "nit": "900111111", "name": "EMPRESA ALFA SAS"},
            {"id": 2, "nit": "800222222", "name": "EMPRESA BETA LTDA"},
            {"id": 3, "nit": "860000001", "name": "TIAN SAS"},
            {"id": 5, "nit": "830050228", "name": "GRUPO ADECCO"},
        ],
        "companies_packages": [
            {"company": 1, "package": 1, "model": "Package"},
            {"company": 2, "package": 1, "model": "Provider"},
            {"company": 3, "package": 1, "model": "Package"},
            {"company": 5, "package": 1, "model": "Special"},
        ],
        "billers": [{"id": 1, "name": "ALFA"}, {"id": 2, "name": "BETA"}],
        "biller_companies": [{"company": 1, "biller": 1}, {"company": 5, "biller": 2}],
        "packages": [{"id": 1, "name": "PAQUETE A 2025"}, {"id": 2, "name": "PAQUETE C 2025"},
                     {"id": 3, "name": "PAQUETE Z"}],
        "providers": [{"id": 1, "name": "PROVEEDOR ALFA"}],
        "specials": [{"id": 1, "name": "ESPECIAL ADECCO"}],
        "cities": [{"id": 1, "name": "BOGOTA, D.C."}, {"id": 2, "name": "MEDELLIN"}, {"id": 3, "name": "CALI"}],
        "activities": ACTIVIDADES,
        "cups": CUPS,
        # El orden importa: el fake devuelve la primera fila que cumple (como hoy PostgreSQL sin ORDER BY) [AUD-05]
        "rates": [
            {"rateable_id": 1, "city_id": 1, "cup_id": 2, "activity_id": 1, "rateable_type": "Package", "rate": 55000},
            {"rateable_id": 2, "city_id": 1, "cup_id": 5, "activity_id": 1, "rateable_type": "Package", "rate": 30000},
            {"rateable_id": 3, "city_id": 3, "cup_id": 1, "activity_id": 1, "rateable_type": "Package", "rate": 41000},
            {"rateable_id": 1, "city_id": 3, "cup_id": 1, "activity_id": 1, "rateable_type": "Provider", "rate": 42000},
            {"rateable_id": 2, "city_id": 1, "cup_id": 3, "activity_id": 1, "rateable_type": "Package", "rate": 12000},
            {"rateable_id": 3, "city_id": 2, "cup_id": 3, "activity_id": 1, "rateable_type": "Package", "rate": 13000},
            {"rateable_id": 3, "city_id": 1, "cup_id": 5, "activity_id": 2, "rateable_type": "Package", "rate": 33000},
            {"rateable_id": 1, "city_id": 1, "cup_id": 1, "activity_id": 1, "rateable_type": "Special", "rate": 0},
        ],
        "imedical": [{"nit_error": "901999999", "name": "EMPRESA ALFA SAS", "nit_success": "900111111",
                      "name_error": "ALFA MAL"}],
        "tian": [{"nit_error": "811000000", "name": "CLIENTE TIAN"}],
    })
    especial, basica = [501, "ESPECIAL ALFA 2026"], [500, "TARIFA BASICA 2025"]
    productos = {c["code"]: 100 + c["id"] for c in CUPS}
    _json(d / "odoo.json", {
        "res.partner": [
            _partner(10, "EMPRESA ALFA S.A.S.", ref_num="900111111", special=especial, base=basica),
            _partner(11, "GRUPO ADECCO", ref_num="830050228"),
            _partner(12, "TIAN SAS", ref_num="860000001", base=basica),
            _partner(13, "EMPRESA GAMMA", vat="700777777-1"),
        ],
        "product.product": [{"id": productos[c["code"]], "name": c["name"], "default_code": c["code"],
                             "list_price": 30000.0} for c in CUPS],
        "account.base.rate": [
            {"id": 501, "name": "ESPECIAL ALFA 2026", "state": "active", "start_date": "2026-01-01", "finish_date": "2026-12-31"},
            {"id": 500, "name": "TARIFA BASICA 2025", "state": "active", "start_date": "2025-01-01", "finish_date": "2025-12-31"},
        ],
        "account.base.rate.line": [
            {"id": 1, "base_rate_id": especial, "city_id": [1, "BOGOTA, D.C."], "product_id": [101, "890201"], "intra": True, "price_unit": 31100.7},
            {"id": 2, "base_rate_id": especial, "city_id": [1, "BOGOTA, D.C."], "product_id": [101, "890201"], "intra": True, "price_unit": 99999.0},
            {"id": 3, "base_rate_id": basica, "city_id": [1, "BOGOTA, D.C."], "product_id": [102, "890202"], "intra": True, "price_unit": 0.0},
            {"id": 4, "base_rate_id": basica, "city_id": [1, "BOGOTA, D.C."], "product_id": [105, "871121"], "intra": False, "price_unit": 27000.0},
            {"id": 5, "base_rate_id": basica, "city_id": [1, "BOGOTA, D.C."], "product_id": [101, "890201"], "intra": True, "price_unit": 25000.0},
        ],
    })
    _json(d / "data.json", [{"nit": "912345678", "name": "EMPRESA RUES SAS", "is_company": True,
                             "checked_bases": "Odoo, RUES", "source": "RUES/NIT"}])


# ─────────────────────────────────────────────────────────────────────────────
VERDE, AMARILLO, NARANJA, AZUL = "E2EFDA", "FFF2CC", "F4B183", "BDD7EE"


def _consolidado(base, ciudad, nit, facturador, paquete, empresa, paciente, ident, facturas, actividad, cups):
    fijos = {"Base": base, "Ingreso N°": "1", "Sede": "SEDE NORTE", "Ciudad": ciudad, "NIT": nit,
             "FACTURADOR": facturador, "Especial / General": "GENERAL" if facturador == "GENERAL" else "ESPECIAL",
             "PAQUETE": paquete, "Empresa": empresa, "Empresa Misión": "MISION SAS", "Medio de Pago": "CREDITO",
             "Fecha Ingreso": "05/10/2026", "Tipo Examen": "INGRESO", "Cargo": "AUXILIAR", "Paciente": paciente,
             "N° Identificación": ident, "Número de Póliza": None, "ORDEN, CENTRO DE COSTO, CECO, PET": "OC-1",
             "ORDEN, CENTRO DE COSTO, CECO, PET_1": None, "FACTURAS": facturas, "TIPO DE ACTIVIDAD": actividad,
             "Observaciones Ingreso": None, "Total": sum(v for v in cups.values() if v)}
    return [fijos[c] for c in CONSOLIDADO_COLS] + [cups.get(c) for c in CUP_COLS]


def opcion7():
    d = RAIZ / "opcion7_prefacturas"
    largo = "COMPANIA DE SERVICIOS TEMPORALES DEL NORTE"   # [AUD-76] mismos 31 primeros caracteres
    filas = [
        CONSOLIDADO_COLS + CUP_COLS,
        _consolidado("OCT", "BOGOTA, D.C.", "900111111", "ALFA", "ESPECIAL ALFA 2026", "EMPRESA ALFA SAS",
                     "ANA PEREZ", "CC 1001", "SET100, FAC200", "INTRA", {"890201": 31100, "890202": 55000}),
        _consolidado("OCT", "BOGOTA, D.C.", "900111111", "ALFA", "ESPECIAL ALFA 2026", "EMPRESA ALFA SAS",
                     "SARA MORA", "1005", "", "INTRA", {"903810-01": 12000}),
        _consolidado("OCT", "BOGOTA, D.C.", "800222222", "GENERAL", "PROVEEDOR ALFA", "EMPRESA BETA LTDA",
                     "MARTA RUIZ", "1003", "SET300", "INTRA", {"871121": 30000}),
        _consolidado("OCT", "CALI", "912345678", "GENERAL", "PAQUETE C 2025", "EMPRESA RUES SAS",
                     "PEDRO DIAZ", "1004", "FAC400", "INTRA", {"890201": 41000}),             # [P-22] FAC → sin factura
        _consolidado("OCT", "CALI", "700777777", "GENERAL", "PAQUETE C 2025", "EMPRESA GAMMA",
                     "LIA SOL", "1011", "SET900", "INTRA", {"890201": 41000}),                # [P-22] mismo NIT,
        _consolidado("OCT", "CALI", "700777777", "GENERAL", "PAQUETE C 2025", "EMPRESA GAMMA",
                     "LUZ MAR", "1014", "", "INTRA", {"890201": 41000}),                      #   dos carpetas
        _consolidado("OCT", "CALI", "555555555", None, "PAQUETE C 2025", "DESCONOCIDA XYZ",
                     "NOE GIL", "1012", "", "INTRA", {"990101": 1}),                          # SIN_FACTURADOR
        _consolidado("OCT", "CALI", None, "ALFA", "PAQUETE C 2025", "SIN NIT",
                     "X", "1099", "", "INTRA", {"890201": 1}),                                # fila sin NIT
        _consolidado("OCT", "BOGOTA, D.C.", "811111111", "ALFA", "PAQUETE A 2025", largo + " A",
                     "P1", "2001", "", "INTRA", {"890201": 100}),
        _consolidado("OCT", "BOGOTA, D.C.", "811111112", "ALFA", "PAQUETE A 2025", largo + " B",
                     "P2", "2002", "", "INTRA", {"890201": 100}),
        _consolidado("OCT", "BOGOTA, D.C.", "822222222", "ALFA", "PAQUETE A 2025", "EMPRESA A/B: SAS",
                     "P3", "2003", "", "EXTRA", {"871121": 33000}),                          # caracteres inválidos
    ]
    n_fijas = len(CONSOLIDADO_COLS)
    col = {c: n_fijas + 1 + i for i, c in enumerate(CUP_COLS)}
    rellenos = {"Consolidado": {
        (2, col["890202"]): VERDE, (3, col["903810-01"]): AZUL, (4, col["871121"]): AMARILLO,
        (5, col["890201"]): NARANJA, (6, col["890201"]): NARANJA, (7, col["890201"]): NARANJA,
        (10, col["890201"]): "FFB6C1",  # color de la "Fase 7" que ya no existe [AUD-56]
    }}
    _libro(d / "CONSOLIDADO.xlsx", {"Consolidado": filas}, rellenos)
    _json(d / "bd.json", {"cups": CUPS})


# ─────────────────────────────────────────────────────────────────────────────
def menu():
    d = RAIZ / "menu_ventana_dias"
    _json(d / "casos.json", {
        "ventana": {"DAY_INITIAL": "5", "DAY_FINAL": "29"},
        "dias": [1, 4, 5, 6, 28, 29, 30, 31],                                   # [AUD-50]
        "configuraciones_invalidas": [                                          # [AUD-30]
            {"DAY_INITIAL": "", "DAY_FINAL": "29"},
            {"DAY_INITIAL": None, "DAY_FINAL": "29"},
        ],
    })


ESCENARIOS = [normalizadores, opcion1, opcion2, opcion6, opcion7, menu]


def main(forzar: bool):
    if RAIZ.exists():
        if not forzar:
            sys.exit(f"{RAIZ} ya existe. Usa --forzar para reconstruirlas (cambia la base del golden).")
        shutil.rmtree(RAIZ)
    for escenario in ESCENARIOS:
        escenario()
    print(f"Entradas construidas en {RAIZ}")


if __name__ == "__main__":
    main("--forzar" in sys.argv)
