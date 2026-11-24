"""Mapas de cuentas analíticas y constantes de plantilla de ETL-Avancys.

Copia literal de `Pipeline.py` (commit 7bb6784, líneas 177-371) para la paridad.
Cambiar un valor cambia la cuenta a la que se imputa cada paciente: hacerlo solo
con una decisión aprobada, igual que se hacía editando Pipeline.py.
"""

import re

# ── Fila interna (Pipeline.py:177-193) ───────────────────────────────────────
COLS_FIJAS = [
    "Proveedor", "Ciudad", "NIT", "Empresa", "Empresa Mision",
    "Fecha Ingreso", "Tipo Examen", "Cargo", "Paciente",
    "N Identificacion", "TOTAL", "CUENTA ANALITICA", "INTRA/EXTRA",
    "Observaciones Ingreso", "Sede", "Ingreso"
]
NUM_COLS_FIJAS = len(COLS_FIJAS)

# Un código de examen son 6 dígitos con sufijo opcional: 890262-01, 954107 (Pipeline.py:198).
RX_CODIGO_EXAMEN = re.compile(r"^\d{6}(-\d{1,2})?$")

# Columnas de la plantilla por nombre exacto (fila 2 del Excel) (Pipeline.py:208-217).
COLUMNAS_REQUERIDAS = [
    "NIT", "Empresa", "Ciudad", "Sede", "Paciente", "N° Identificación",
    "Ingreso N°",
]
COLUMNAS_OPCIONALES = [
    "Base", "Empresa Misión", "Fecha Ingreso", "Tipo Examen", "Cargo",
    "Observaciones Ingreso",
]

# ── Ciudad → cuenta analítica (Pipeline.py:225-289) ──────────────────────────
CIUDAD_CUENTA = {
    "ACACIAS": "AA10814", "AGUACHICA": "AA10493", "AGUAZUL": "AA10784",
    "APARTADO": "AA10726", "ARAUCA": "AA10674", "ARMENIA": "AA8649",
    "BARBOSA": "AA10785", "BARRANCABERMEJA": "AA10702", "BARRANCAS": "AA10615",
    "BARRANQUILLA": "AA10319", "BELLO": "AA11096", "BOGOTA D.C.": "AA8638",
    "BOGOTA": "AA8638", "BUENAVENTURA": "AA8655",
    "BUGA": "AA10460", "CAJICA": "AA10573", "CALI": "AA10405",
    "CARTAGENA": "AA13039", "CARTAGO": "AA10685", "CAUCASIA": "AA10700",
    "CHIA": "AA10703", "CHINCHINA": "AA11098", "CHIQUINQUIRA": "AA8663",
    "CIMITARRA": "AA10572", "COTA": "AA10687", "CUCUTA": "AA10564",
    "DOSQUEBRADAS": "AA10581", "DUITAMA": "AA8666", "EL COCUY": "AA10770",
    "ESPINAL": "AA10718", "FACATATIVA": "AA8668", "FLORENCIA": "AA10584",
    "FUNZA": "AA10825", "FUSAGASUGA": "AA10577", "GACHANCIPA": "AA10803",
    "GIRARDOT": "AA10826", "GRANADA": "AA10742", "GUADUAS": "AA10734",
    "GUAYABAL DE SIQUIMA": "AA10763", "HONDA": "AA10801",
    "INIRIDA": "AA10597", "IPIALES": "AA10540", "ITAGUI": "AA11088",
    "LA CALERA": "AA10689", "LA DORADA": "AA10707", "LA JAGUA DE IBIRICO": "AA10828",
    "LA MESA": "AA11086", "LA PLATA": "AA10766", "LETICIA": "AA10829",
    "LIBANO": "AA11130", "MADRID": "AA10614", "MAGANGUE": "AA10773",
    "MALAMBO": "AA12778", "MANIZALES": "AA10326", "MEDELLIN": "AA8641",
    "MELGAR": "AA8682", "MIRAFLORES": "AA10764", "MITU": "AA10604",
    "MOCOA": "AA10504", "MONIQUIRA": "AA11080", "MONTELIBANO": "AA8684",
    "MONTERIA": "AA10330", "MONTERREY": "AA10592", "NEIVA": "AA10328",
    "OCANA": "AA10612", "ORITO": "AA10720", "PACHO": "AA11083",
    "PALMIRA": "AA10010", "PAMPLONA": "AA10699", "PASTO": "AA10325",
    "PAZ DE ARIPORO": "AA12935", "PITALITO": "AA8691",
    "PLANETA RICA": "AA10282", "POPAYAN": "AA10698", "PUERTO ASIS": "AA8693",
    "PUERTO BERRIO": "AA10598", "PUERTO BOYACA": "AA8695", "PUERTO GAITAN": "AA10550",
    "PUERTO LOPEZ": "AA10741", "QUIBDO": "AA8701", "RIOHACHA": "AA10772",
    "RIONEGRO": "AA8704", "RISARALDA": "AA10743", "SABANA TORRES": "AA10603",
    "SABANALARGA": "AA10692", "SAHAGUN": "AA10834", "SAN ANDRES": "AA8705",
    "SAN GIL": "AA8706", "SAN JOSE DEL GUAVIARE": "AA10595",
    "SAN VICENTE DEL CAGUAN": "AA10725", "SANTA MARTA": "AA10324",
    "SANTA ROSA DE VITERBO": "AA11138", "SANTAFE DE ANTIOQUIA": "AA13116",
    "SANTANDER DE QUILICHAO": "AA10836", "SARAVENA": "AA10837",
    "SINCELEJO": "AA10327", "SOACHA": "AA10690", "SOGAMOSO": "AA8711",
    "SOLEDAD": "AA13056", "TAME": "AA10717", "TAURAMENA": "AA10576",
    "TOCANCIPA": "AA10463", "TULUA": "AA10461", "TUMACO": "AA8713",
    "TUNJA": "AA10841", "UBATE": "AA10606", "URRAO": "AA10750",
    "VALLEDUPAR": "AA10329", "VILLA DE LEYVA": "AA10807", "VILLA GARZON": "AA8700",
    "VILLANUEVA": "AA10728", "VILLAVICENCIO": "AA8719", "YARUMAL": "AA10767",
    "YOLOMBO": "AA11097", "YOPAL": "AA10587", "ZIPAQUIRA": "AA10691",
    # SAN ALBERTO faltaba: el fuzzy la emparejaba con SAN GIL (score 86) y
    # los 5 pacientes de CONSULTORIA Y GESTION AMBIENTAL (factura 726406)
    # se imputaron a Santander. La cuenta correcta siempre existio.
    "SAN ALBERTO": "AA11207",
    # SAN JUAN DEL CESAR no estaba en el mapa: se resolvia por nombre (paso 5)
    # y funcionaba, pero con un WARNING en cada corrida. Ya tiene codigo
    # propio, asi que entra al mapa como todas.
    "SAN JUAN DEL CESAR": "AA11216",
    # IBAGUE apuntaba a AA10423 (INTRAMURAL - SEDE IBAGUE), pero SOA ya no
    # tiene sede propia ahi: los 26 pacientes de octubre los atendio un
    # tercero (SOMOS MEDICINA OCUPACIONAL) y van a proveedores.
    "IBAGUE": "AA10323",
    # BUCARAMANGA era el caso contrario: apuntaba a AA10739 (EXTRAMURAL) y
    # ahi SI hay sede propia — los 53 pacientes de octubre traen
    # "Sede = BUCARAMANGA". Va a la cuenta de la sede.
    "BUCARAMANGA": "AA8643",
    # PEREIRA vuelve al mapa: estaba por id porque su cuenta de proveedores
    # llevaba el AA13039 de CARTAGENA. Ya tiene el suyo (AA11120). Y es la
    # de proveedores, no AA8644 (INTRAMURAL - SEDE PEREIRA): SOA ya no tiene
    # sede propia alli — los 39 pacientes de octubre los atendio A&A
    # PROTECCION INTEGRAL, un tercero.
    "PEREIRA": "AA11120",
}

# ── Ciudades cuya cuenta se carga por ID (la cuenta no tiene código) (Pipeline.py:301-303)
CIUDAD_CUENTA_ID = {
    "MARIQUITA": 11136,   # SEDE SOA - PROVEEDORES - MARIQUITA (sin codigo)
}

# ── Sede → cuenta: manda sobre CIUDAD_CUENTA (Pipeline.py:321-324) ──────────
SEDE_CUENTA = {
    "SEDE 103":        "AA8638",   # INTRAMURAL - SEDE 103 - BOGOTA D.C.
    "ZONA INDUSTRIAL": "AA8637",   # INTRAMURAL - ZONA INDUSTRIAL - BOGOTA D.C.
}

# ── Familias de cuenta (Pipeline.py:350-371) ─────────────────────────────────
FAMILIA_INTRAMURAL = "INTRAMURAL"
FAMILIA_EXTRAMURAL = "EXTRAMURAL"
FAMILIA_PROVEEDOR = "PROVEEDOR"

# Lo que en la columna Sede significa "SOA fue hasta el sitio del cliente".
SEDES_EXTRAMURALES = ("EXTRAMURAL",)

# Rama genérica preferida cuando una ciudad tiene varias cuentas de la misma familia.
RAMA_PRIORIDAD = (
    "SALUD OCUPACIONAL DE LOS ANDES LTDA",
    "SEDE SOA",
    "GRUPO ALTUM",
)

# Puntaje mínimo de rapidfuzz para aceptar una ciudad por parecido.
UMBRAL_CIUDAD = 95
