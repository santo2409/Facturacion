# Análisis de ETL-Avancys

Análisis en **solo lectura** de `/home/santiagosoa/Desarrollo/ETL-Avancys` (commit `7bb6784`, 2026-10-29;
referencias de línea verificadas de nuevo el 2026-11-09).
No se modificó nada en esa carpeta. No se leyeron `.env` ni `.env.example` (bloqueados por permisos):
los nombres de variables salen del código y del README.

**Qué es.** Un único script, `Pipeline.py` (1.911 líneas), que lee en lote las pre-facturas `.xlsx`
que genera la opción 7 de Facturacion y crea **una factura borrador (`account.move`, `out_invoice`)
por empresa (NIT)** en Odoo 14 por XML-RPC. Nunca publica, nunca crea terceros. Proceso mensual y manual.
Según el README, el mismo archivo vive también en el repositorio interno **Facturas-Avancys**
(`_buscar_datos`, `Pipeline.py:44-57`, acepta `datos/` o `archivo/datos/`).

Las referencias `Pipeline.py:N` son de ETL-Avancys; las rutas `src/...`, `tests/...` y `main.py` son de Facturacion.

---

## 1. Extracción

| Aspecto | Detalle | Referencia |
|---|---|---|
| Fuente principal | Archivos `.xlsx` de `datos/Entrada/` (solo el nivel superior, `os.listdir`). Se excluyen los `~$*` y los que contienen `consolidado` | `Pipeline.py:87`, `1682-1687` |
| Hoja leída | La primera hoja (`pd.read_excel` sin `sheet_name`), que en las pre-facturas de la opción 7 es `BASE GENERAL`. La hoja `Leyenda` se ignora | `Pipeline.py:874`; `src/preInvoice/application/use_cases/split_by_nit.py:213`, `:366` |
| Lectura | `pd.read_excel(ruta, header=None, dtype=str)`: todo como texto. Fila 1 (nombres de examen) no se lee; fila 2 = encabezados; datos desde la fila 3 | `Pipeline.py:874-878` |
| Constantes muertas | `FILA_HEADER = 5` y `FILA_DATOS = 6` no se usan (la lectura real usa `iloc[1]` y `iloc[2:]`) | `Pipeline.py:219-220` |
| Fuente secundaria (Odoo, lectura) | `res.partner` (cliente por `ref_num`), `product.product` (por `default_code`), `account.analytic.account` (índice completo de cuentas + búsqueda por `code`), `account.tax` (por nombre), `uom.uom` (por nombre), `account.move` (guarda anti-duplicados) | `Pipeline.py:398`, `627`, `643`, `720`, `796`, `818`, `848`, `1260` |
| Autenticación | XML-RPC `/xmlrpc/2/common` → `authenticate(DB, USER, API_KEY)`; `/xmlrpc/2/object` → `execute_kw`. Variables: `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_API_KEY`. Si falta una, `SystemExit` con el nombre | `Pipeline.py:73-85`, `536-552` |
| Variables de pruebas | `ODOO_TEST_URL`, `ODOO_TEST_DB`, `ODOO_TEST_USER`, `ODOO_TEST_API_KEY` existen en el `.env` según el README, pero el código **no las lee**: para ensayar hay que cambiar el código o el entorno | README "Credenciales"; `Pipeline.py:82-85` |
| Carga del `.env` | Parser propio (sin `python-dotenv`): busca `.env` hacia arriba desde el archivo y usa `os.environ.setdefault`, así que **el entorno del sistema gana sobre el `.env`** (al revés que Facturacion) | `Pipeline.py:60-70`; `src/shared/env.py` (`override=True`) |
| Filtros | Archivo: plantilla válida (7 columnas obligatorias por nombre exacto). Fila: sin NIT se descarta (y se reporta). Empresa: `EMPRESAS_BLOQUEADAS` (por prefijo de nombre normalizado), `NITS_BLOQUEADOS`, `YA_SUBIDAS` | `Pipeline.py:147-175`, `208-217`, `880-895`, `986-992`, `1050-1070` |
| Paginación | No hay. Cada consulta es individual (cliente por empresa, producto por código, cuenta por ciudad/sede), con cachés en memoria por corrida. La única consulta masiva es el índice de **todas** las cuentas analíticas, sin `limit` | `Pipeline.py:385-407`, `619-646` |
| Frecuencia | Mensual, ejecución manual (`./venv/bin/python Pipeline.py`). No hay programador | README "El proceso de cada mes" |

## 2. Transformación

### 2.1 Lectura y validación del archivo
| # | Regla | Referencia |
|---|---|---|
| T1 | Columnas obligatorias (nombre exacto en fila 2): `NIT`, `Empresa`, `Ciudad`, `Sede`, `Paciente`, `N° Identificación`, `Ingreso N°`. Si falta una → `ValueError`, el archivo se copia a `Salida/verificar/` y encabeza el log como ERROR | `Pipeline.py:208-211`, `881-890`, `1740-1743`, `1783-1788` |
| T2 | Columnas opcionales: `Base`, `Empresa Misión`, `Fecha Ingreso`, `Tipo Examen`, `Cargo`, `Observaciones Ingreso`. Si faltan → WARNING, sigue | `Pipeline.py:214-217`, `891-895` |
| T3 | Columna de examen = encabezado que cumple `^\d{6}(-\d{1,2})?$`, tras quitar un sufijo literal `.0`. Se detectan por forma, no por posición | `Pipeline.py:198`, `901-910` |
| T4 | `get_val`: `None`, NaN, `""`, `"nan"`, `"NaN"` → `None`; si no, texto con `strip()` | `Pipeline.py:914-919` |
| T5 | Celda de examen "con valor" si no es `None`, `""`, `nan`, `NaN`, `0`, `0.0`. Se guarda como número (`_a_numero`: quita `$` y `,`, `float`; si falla → `1`). Ese valor **no** va a Odoo: solo sirve para el libro de pendientes | `Pipeline.py:960-976` |
| T6 | Mapeo a la fila interna (`COLS_FIJAS`): `Empresa Misión`→`Empresa Mision`, `N° Identificación`→`N Identificacion`, `Ingreso N°`→`Ingreso`; constantes `Proveedor=None`, `TOTAL=0`, `CUENTA ANALITICA=None`, `INTRA/EXTRA="TRUE"` (no se usan después) | `Pipeline.py:177-182`, `929-949` |
| T7 | Período: cuenta los valores de `Base`; si hay más de un "mes" (penúltima palabra) → WARNING | `Pipeline.py:1752-1761` |

### 2.2 Agrupación
| # | Regla | Referencia |
|---|---|---|
| T8 | Agrupa **todas** las filas de **todos** los archivos por el texto de `NIT` (sin normalizar, solo `strip`). El nombre de la empresa es el de la **última** fila leída de ese NIT | `Pipeline.py:981-997` |
| T9 | Filas sin NIT → log ERROR con paciente y archivo (máx. 20), no se facturan | `Pipeline.py:985-1005` |
| T10 | Orden de proceso: inserción en el dict = orden alfabético de archivos y luego de filas | `Pipeline.py:1682`, `1794` |

### 2.3 Por empresa (`crear_factura_odoo`)
| # | Regla | Referencia |
|---|---|---|
| T11 | Aviso "cobro doble": mismo (`N Identificacion`, `Ingreso`) en ≥2 filas **con el mismo examen** en ambas. Solo avisa | `Pipeline.py:1025-1045` |
| T12 | Empresa bloqueada por nombre (normalizado sin tildes, prefijo) → VERIFICAR, sin tocar Odoo | `Pipeline.py:1050-1056` |
| T13 | `YA_SUBIDAS[nit_limpio]` → OK con la factura indicada, sin crear | `Pipeline.py:1058-1064` |
| T14 | `NITS_BLOQUEADOS` → VERIFICAR | `Pipeline.py:1066-1070` |
| T15 | NIT válido: quitar `-` y `.`, solo dígitos, 6 a 12 caracteres | `Pipeline.py:866-868` |
| T16 | Cliente: `res.partner` con `ref_num in {nit, nit_limpio}`, `limit 2`. 0 → VERIFICAR "Sin tercero"; 2 → VERIFICAR (varios terceros); 1 → cliente. **Nunca por nombre, nunca por `vat`**. `SequenceMatcher` < 0,60 entre nombres solo genera WARNING | `Pipeline.py:835-864`, `1072-1083` |
| T17 | Impuestos: `AUTORRETENCION IMPUESTO RENTA 2%` y `AUTORRETENCION COMPRA IMPUESTO RENTA 2%`, nombre exacto con `type_tax_use in (sale, all)`; si no, `ilike` con los primeros 20 caracteres (toma el primero). Los que se encuentren van a **todas** las líneas | `Pipeline.py:124-125`, `791-811`, `1088-1101`, `1189-1190` |
| T18 | UdM: `Unidades`, exacto y si no `ilike` | `Pipeline.py:128`, `814-833` |
| T19 | Cuenta analítica por paciente (`resolver_cuenta_analitica`, caché por (ciudad, sede)): 1) `SEDE_CUENTA` (SEDE 103→AA8638, ZONA INDUSTRIAL→AA8637), validando que la cuenta sea de la ciudad de la fila; 2) sede con `EXTRAMURAL` → cuenta EXTRAMURAL de la ciudad por nombre; 3) `CIUDAD_CUENTA_ID` (MARIQUITA→11136); 4) `CIUDAD_CUENTA` (~120 ciudades) con desempate por nombre si el código está repetido o ya no existe; 5) ciudad fuera del mapa → cuenta PROVEEDORES por nombre. **Sin fallback**: si no se resuelve, el paciente se aparta | `Pipeline.py:225-343`, `649-788`, `1106-1138` |
| T20 | Normalización de ciudad: mayúsculas, sin tildes (NFD), sin nada que no sea `A-Z0-9`. Emparejamiento: exacto → por palabra completa (prefijos/sufijos) → `rapidfuzz WRatio` ≥ 95 con ganador único | `Pipeline.py:330-339`, `410-430`, `452-466` |
| T21 | Familia de cuenta por el nombre: `PROVEEDORES` / `INTRAMURAL` / `EXTRAMURAL`; desempate de rama: `SALUD OCUPACIONAL DE LOS ANDES LTDA` > `SEDE SOA` > `GRUPO ALTUM`; otras ramas nunca se eligen solas | `Pipeline.py:350-382`, `433-450` |
| T22 | Líneas: una por (código de examen, cuenta analítica), `quantity` = número de pacientes con ese examen (no suma valores), orden `sorted(..., key=str((código, cuenta)))` | `Pipeline.py:1110-1138`, `1148` |
| T23 | Producto por `default_code` = código del encabezado **tal cual** (con sufijo). Si no existe → examen a pendientes "PRODUCTO NO ENCONTRADO" (solo pacientes con cuenta resuelta) | `Pipeline.py:624-631`, `1149-1170` |
| T24 | Línea: `product_id`, `quantity`, `price_unit = list_price` del producto, `name = nombre del producto`, `account_id` = 42650 (gravados) si `default_code` ∈ `PRODUCTOS_GRAVADOS` (`["100006"]`), si no 42653 (excluidos); `tax_ids (6,0,[...])`, `product_uom_id`, `analytic_account_id` | `Pipeline.py:113-119`, `1172-1200` |
| T25 | Cuadre: exámenes del archivo = cantidades en líneas + pendientes; si no → "DESCUADRE" (log ERROR y aviso en el detalle) | `Pipeline.py:1211-1225` |
| T26 | Sin líneas → VERIFICAR | `Pipeline.py:1227-1237` |
| T27 | Cabecera: `move_type=out_invoice`, `partner_id`, `journal_id=47`, `state=draft`, `narration="Pre-factura automatica. Pacientes: N"` (N = filas, no cédulas únicas). **Sin fechas** (`invoice_date`, `invoice_date_due`, `date_of_service`, `range_id`) | `Pipeline.py:110`, `1243-1250` |
| T28 | Tras crear: `write invoice_date_due=False` (Odoo lo calcula al crear) | `Pipeline.py:579-590`, `1278` |
| T29 | `ACTUALIZAR_PRECIOS=False`: las líneas suben con `list_price` (en la práctica 1) y el precio se trae a mano con el botón de Odoo. Si fuera `True`, se llama `update_puchase_line_prices` por JSON-RPC | `Pipeline.py:138`, `557-613`, `1825-1835` |
| T30 | Constantes definidas y **no usadas**: `CUENTA_RECEIVABLE` (40921), `CUENTA_PAYABLE` (41977) | `Pipeline.py:115-116` |

## 3. Carga

| Aspecto | Detalle | Referencia |
|---|---|---|
| Destino | Odoo (producción por defecto): `account.move.create` + `write` del vencimiento. Ningún otro modelo se escribe | `Pipeline.py:1276-1278` |
| Formato | Diccionario de valores con líneas `(0, 0, {...})` (comando one2many) | `Pipeline.py:1180-1200`, `1243-1250` |
| Estrategia | Solo **insert** (un `create` por empresa). No hay upsert ni reemplazo | `Pipeline.py:1276` |
| Idempotencia | Guarda: antes de crear busca `account.move` `out_invoice`, mismo `partner_id`, `journal_id=47`, `state=draft`, `create_uid=uid`, `create_date >= hoy 00:00` (hora local comparada con UTC). Si existe → OK "Ya existia". Solo protege **el mismo día**; un lote de otro día se duplica. `YA_SUBIDAS` es el mecanismo manual entre días | `Pipeline.py:1252-1274`, `154-166` |
| Transacciones | Cada `create` es atómico en Odoo (la factura y sus líneas). No hay transacción entre empresas: lo creado queda creado | — |
| Salidas locales | `Salida/log_inyeccion.xlsx` (hoja "Log Inyeccion", 10 columnas + totales), `log_inyeccion.txt`, `facturas_creadas.csv` (`factura_id;nit;empresa;url`), `pendientes_facturador.xlsx` (hojas "Subir a mano" y "Empresas sin factura"), `cuentas_por_revisar.xlsx` ("Arreglar en Odoo"), `Salida/verificar/` (copias de archivos ilegibles) | `Pipeline.py:88-99`, `1403-1667` |
| Reversión | `facturas_creadas.csv` se escribe factura a factura "para poder revertir", pero se **trunca al iniciar cada corrida** (`open(..., "w")`) | `Pipeline.py:1791-1792`, `1837-1841` |

## 4. Errores y reintentos

| Situación | Comportamiento | Referencia |
|---|---|---|
| Conexión inicial | 3 intentos, 5 s entre ellos; al tercero propaga y aborta | `Pipeline.py:536-552`, `1774` |
| Timeout XML-RPC | **No hay** (`ServerProxy` sin transporte con timeout). Solo el JSON-RPC de precios tiene 180 s | `Pipeline.py:540`, `544`, `572` |
| Archivo ilegible o plantilla cambiada | Se aparta (copia a `verificar/`) y sigue con los demás | `Pipeline.py:1740-1743` |
| Error de red durante una empresa (`OSError`, `ProtocolError`) | Reintenta la empresa completa hasta 3 veces, 10 s y reconexión; la guarda anti-duplicados hace seguro el reintento si la factura se creó y se perdió la respuesta. Tras 3 → ERROR y sigue | `Pipeline.py:1798-1817` |
| Otro error en una empresa | ERROR con el mensaje (150 caracteres) y sigue con la siguiente | `Pipeline.py:1818-1821` |
| Fallo al borrar el vencimiento | WARNING; la factura queda con vencimiento | `Pipeline.py:586-590` |
| Corte a mitad de corrida | Lo creado queda en Odoo. Los libros se reescriben cada 10 empresas y al final; `facturas_creadas.csv` tiene lo creado hasta el corte. Para repetir el mismo día protege la guarda; otro día, `YA_SUBIDAS` a mano | `Pipeline.py:1855-1862` |
| Efecto lateral del reintento | `_pendiente` suma en `REVISAR` (exámenes, valor) cada vez que se llama; si una empresa se reintenta tras haber calculado pendientes, `cuentas_por_revisar.xlsx` **cuenta doble**. `PENDIENTES` no se duplica (se agrega en `_guardar_pendientes`) | `Pipeline.py:1343-1386` |
| Impuesto/UdM no encontrados | WARNING; las líneas salen sin impuesto o sin UdM (no aborta) | `Pipeline.py:807-811`, `829-833`, `1098-1101` |

## 5. Dependencias y versiones

| | ETL-Avancys | Facturacion |
|---|---|---|
| Python | 3.12 (probado 3.12.3) | 3.12+ (venv local 3.13) |
| pandas | 3.0.5 | **no está** (usa Polars 1.36.1 + fastexcel 0.18.0) |
| openpyxl | 3.1.5 | 3.1.5 (igual) |
| rapidfuzz | 3.14.6 | 3.14.3 (distinta) |
| `.env` | parser propio, sin dependencia | python-dotenv 1.2.1 |
| stdlib | `xmlrpc.client`, `urllib.request` (JSON-RPC), `difflib.SequenceMatcher`, `unicodedata`, `logging` | `xmlrpc.client` con transporte con timeout (AUD-11), `unidecode` 1.4.0 |
| Servicio externo | Odoo 14 (Avancys) en `ODOO_URL`; método propio de Avancys `account.move.update_puchase_line_prices` (solo si `ACTUALIZAR_PRECIOS`); campo propio `res.partner.ref_num` | El mismo Odoo y `ref_num`; además PostgreSQL (Supabase) y RUES |

Fuente: `ETL-Avancys/requirements.txt`; `Facturacion/requirements.txt`.

## 6. Solapamiento con Facturacion

Revisado leyendo ambos códigos (2026-11-09). `P:N` = `ETL-Avancys/Pipeline.py:N`; las rutas `src/…`, `tests/…` y `main.py` son de Facturacion.
Abreviaturas: `xmlrpc` = `src/odooInjection/infrastructure/odoo/xmlrpc_odoo_repository.py`;
`inject` = `src/odooInjection/application/use_cases/inject_invoices_to_odoo.py`.

**Decisión**: *Reutilizar tal cual* (mismo comportamiento, verificado) · *Reutilizar adaptando* (se extiende lo de
Facturacion sin cambiar su comportamiento actual; el golden sigue en verde) · *Mantener del ETL* (lógica que Facturacion
no tiene o tiene distinta) · *Descartar* (Facturacion ya lo resuelve).
**Riesgo para la paridad**: *Alto* = cambia lo que se envía a Odoo en los casos de `tests/paridad/entradas`;
*Medio* = cambia libros, mensajes o casos fuera de la captura; *Bajo* = sin efecto observable.

**Restricción que condiciona las decisiones.** El golden `opcion8_inyeccion` congela el flujo actual de `src/odooInjection`
(lector, `CityAccountResolver`, `find_client`, `ExcelLogGenerator`). Cambiar esas clases rompe el golden (regla 3), así que
lo que difiere del ETL se decide como *Mantener del ETL* en clases nuevas, no como *Reutilizar adaptando*. Qué hacer con el
flujo viejo sigue abierto (E-13).

### 6.1 Configuración y `.env`

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| `_cargar_env`: parser propio, busca `.env` hacia arriba desde el script | `load_env` (python-dotenv) | P:60-70 · `src/shared/env.py:14-21` | **Precedencia invertida.** ETL usa `os.environ.setdefault` y gana el entorno (P:69); Facturacion usa `override=True` y gana el `.env` (`env.py:20`). El parser del ETL solo quita comillas de los extremos (P:69), sin `export` ni escapes | Descartar | Bajo para la salida. Operativo: una variable exportada en la shell que hoy manda en el ETL dejará de mandar |
| `_env`: si falta una variable obligatoria, `SystemExit` con su nombre | `get_odoo_config` (valor por defecto `""`) + validación en el controller | P:73-77, `82-85` · `src/odooInjection/config.py:15-18`; `inject_invoices_controller.py:26-31` | El ETL exige las cuatro variables y aborta antes de leer archivos. Facturacion solo valida `ODOO_USERNAME` y `ODOO_API_KEY`; sin `ODOO_URL` o `ODOO_DB` falla al conectar. **Usuario**: `ODOO_USER` (P:84) frente a `ODOO_USERNAME` (`config.py:17`) | Reutilizar adaptando (añadir URL y DB a la validación sin cambiar el mensaje actual) | Bajo |
| Constantes de negocio: diario 47, cuentas 42653/42650, impuestos, UdM, `PRODUCTOS_GRAVADOS=["100006"]` | Las mismas como variables de entorno, con los mismos valores por defecto | P:110-128 · `config.py:19-38` | Mismos valores por defecto. `ODOO_PRODUCTOS_GRAVADOS.split(",")` no quita espacios (`config.py:28`): con `"100006, 890202"`, `" 890202"` no coincide (AUD-63, congelado en el golden `opcion8`). En el ETL es una lista literal. `CUENTA_RECEIVABLE`/`PAYABLE` no se usan en el ETL (P:115-116); en Facturacion solo las usa `create_client` (`xmlrpc:337-348`) | Reutilizar tal cual | Bajo con los valores por defecto; Medio si alguien define la variable con espacios |
| Configuración que se edita cada mes: `NITS_BLOQUEADOS`, `EMPRESAS_BLOQUEADAS`, `YA_SUBIDAS`, `ACTUALIZAR_PRECIOS` | No existe | P:138, `147-175` · — | Sin ellas, `900448167` se facturaría (en la captura sale VERIFICAR) y `SGS COLOMIA…` también | Mantener del ETL (dónde guardarla: E-04) | Alto |
| Mapas de cuentas: `CIUDAD_CUENTA` (~120 ciudades), `CIUDAD_CUENTA_ID`, `SEDE_CUENTA`, `RAMA_PRIORIDAD`, `UMBRAL_CIUDAD=95` | `CIUDAD_CUENTA` antiguo + `CUENTA_ANALITICA_FALLBACK="AA8638"` | P:225-327, `356-371` · `src/odooInjection/domain/entities/city_account_map.py:1-…` | Facturacion tiene la versión anterior a la corrección de octubre-2026: códigos repetidos (`BELLO` y `CHINCHINA` → `AA10801`, `city_account_map.py:7`, `:11`), sin sedes, sin MARIQUITA por id y con respaldo a Bogotá | Mantener del ETL | Alto |

### 6.2 Conexión a base de datos

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| No usa base de datos: solo Excel y Odoo (no importa sqlalchemy ni psycopg) | `engine` y `get_session` de Supabase | P:1-21 (imports) · `src/shared/database/database.py:17-35` | `database.py` crea el `engine` **al importarse** (`:30`). No conecta hasta el primer uso (`pool_pre_ping`), pero lee `SUPABASE_DB_*`. El flujo integrado no necesita BD | Mantener del ETL (el flujo de inyección no toca la BD; el controller no llama a `get_session()`) | Bajo |

### 6.3 Cliente de Odoo y búsqueda de partners

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| `conectar`: 3 intentos, 5 s entre ellos | `XmlRpcOdooRepository.connect` | P:536-552 · `xmlrpc:73-93`, transportes `xmlrpc:10-50` | Misma lógica. Facturacion añade un timeout de socket de 180 s (`ODOO_TIMEOUT_SECONDS`, AUD-11); el ETL no tiene timeout en XML-RPC (P:540, `544`). El comentario de `xmlrpc:10` ("mismo valor que usa ETL-Avancys") se refiere en realidad al JSON-RPC de precios (P:572). Los textos de log difieren en tildes ("conexión") | Reutilizar tal cual (diferencia de timeout aceptada; E-11) | Bajo en el simulador. En el Odoo real, un `create` de más de 180 s se cortaría, pero el reintento con la guarda no duplica |
| Reintento por empresa ante fallos de red: 3 intentos, 10 s y reconexión | No existe: cualquier excepción → ERROR | P:1798-1821 · `inject:218-220` | Con un corte de red, el ETL reintenta la empresa; Facturacion la marca ERROR y sigue | Mantener del ETL | Medio (la captura no tiene fallos de red) |
| `buscar_cliente`: `ref_num in {nit, nit_limpio}`, `limit 2`; si hay más de uno → VERIFICAR; nunca por nombre | `find_client` → `_find_partners_by_document` + respaldo por nombre en el caso de uso | P:835-864 · `xmlrpc:111-113`, `121-126` (etapas), `141-188`; `inject:131-137`; `find_client_by_name` `xmlrpc:296-305` | (a) Facturacion busca también por `vat` y por `=like nit%`, así que encuentra terceros que el ETL no. (b) **Duplicados**: el ETL rechaza (P:853-856); Facturacion se queda con el de menor id (`xmlrpc:166`, `185`). (c) **Respaldo por nombre** con `ilike` (`inject:133-134`), justo lo que el ETL prohíbe (docstring P:836-843). (d) Facturacion normaliza con `normalize_nit` (`xmlrpc:177`), que se queda con los 9 primeros dígitos | Mantener del ETL (método nuevo en el adaptador; `find_client` lo usan otras opciones y no se toca) | **Alto**: en la captura, `901000003` (dos terceros) sale VERIFICAR; con `find_client` se facturaría al tercero 508 |
| Aviso de nombre distinto: `SequenceMatcher` < 0,60 solo genera WARNING | `CompanyNameMatcher` (rapidfuzz, umbral 90) | P:857-863 · `src/shared/utils/company_name_matcher.py:8-34` | Otro algoritmo, otro umbral y otro propósito: en Facturacion decide el emparejamiento por nombre; en el ETL solo avisa | Mantener del ETL | Bajo (solo afecta al log) |
| `buscar_producto` | `find_product` | P:624-631 · `xmlrpc:100-109` | Ninguna: mismo dominio, mismos campos, `limit 1`, caché por código | Reutilizar tal cual | Bajo |
| `buscar_tax_id` | `find_tax` + `_resolve_taxes` | P:791-811 · `xmlrpc:361-380`; `inject:101-109` | `limit` 5/10 en el ETL frente a 1/5; `False` frente a `None` si no lo encuentra. El resultado es el mismo: ambos toman `r[0]` y ambos descartan el valor falso (P:1093-1097) | Reutilizar tal cual | Bajo |
| `buscar_uom_id` | `find_uom` | P:814-833 · `xmlrpc:382-397` | `limit` 5 frente a 1 en el `ilike`; `False`/`None`. Mismo resultado: la línea solo lleva `product_uom_id` si hay valor (P:1191-1192, `inject:175-176`) | Reutilizar tal cual | Bajo |
| `resolver_cuenta_analitica`: sede → EXTRAMURAL → id → código confirmado por nombre → PROVEEDORES por nombre; si no se resuelve, el paciente se aparta | `CityAccountResolver.resolve` + `find_analytic_account` | P:388-407 (índice), `410-430`, `632-646`, `649-788`; `1106-1138` · `src/odooInjection/domain/services/city_account_resolver.py:10-35`; `xmlrpc:350-359`; `inject:141-147` | Facturacion no mira la sede; usa `WRatio ≥ 80` (`city_account_resolver.py:10`, `32-34`) frente a ≥ 95 con ganador único (P:371, `420-428`); cuando no resuelve, usa **Bogotá AA8638**; busca por código con `limit 1` (`xmlrpc:356`), así que con un código repetido elige mal | Mantener del ETL | **Alto**: en la captura, ZONA INDUSTRIAL → AA8637 (ETL) frente a AA8638; PUEBLO INVENTADO → apartado frente a Bogotá; TABIO → PROVEEDORES TABIO y MARIQUITA → id 11136, frente a Bogotá en ambos; SEDE 103 en CALI → apartado frente a CALI (comprobado ejecutando `CityAccountResolver.resolve`) |
| `account.move.create` + `write` que borra el vencimiento | `create_invoice` (sin `write`) | P:1276-1278, `579-590` · `xmlrpc:415-416` | Facturacion no borra el vencimiento (además lo envía, ver 6.5) | Reutilizar adaptando (añadir al adaptador un método que borre el vencimiento) | Medio |
| Guarda anti-duplicados en Odoo: borrador del mismo tercero, diario, usuario y día | Anti-duplicados por log local (NIT con estado OK en `log_inyeccion.xlsx`) | P:1252-1274 · `inject:51-62`; `src/odooInjection/infrastructure/reporting/excel_log_generator.py:20-34`; ADR-009 | El log local omite empresas OK de **cualquier** corrida previa; la guarda del ETL solo cubre el mismo día y devuelve "Ya existia" con el id | Mantener del ETL (sumar el log local: E-03) | Alto si se suma el log local (cambia el resultado de la segunda corrida) |
| Nunca crea terceros | Regla ADR-010; `create_client` existe pero el caso de uso no lo llama | Sin `create` sobre `res.partner` en el ETL (solo P:1276) · `xmlrpc:337-348`; `inject:131-137` | Misma regla | Reutilizar tal cual (no llamar `create_client`) | Bajo |
| Enlace a la factura: `URL/web#id=…&model=account.move&view_type=form` | Mismo formato | P:530-531 · `inject:210` | Ninguna | Reutilizar tal cual | Bajo |

### 6.4 Normalización de NIT y de texto

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| `nit_valido`: quita `-` y `.`; 6 a 12 dígitos | `normalize_nit` (solo dígitos, primeros 9); `clean_digits`, `classify_document` | P:866-868 · `src/shared/utils/text_normalizer.py:48-53`; `src/shared/utils/document_normalizer.py:31-35`, `45-56` | Con DV, `"900111111-1"`: el ETL busca `ref_num in {"900111111-1", "9001111111"}` y **no encuentra** un tercero con `ref_num="900111111"`; Facturacion normaliza a `900111111` y sí lo encuentra. `"12345"`: el ETL → VERIFICAR (NIT inválido; evita `ref_num='1'`, CLIENTES MOSTRADOR); Facturacion lo busca. Cédulas de 10 dígitos: Facturacion las corta a 9 | Mantener del ETL | **Alto** (DV pegado y NIT cortos) |
| Agrupación por el texto del NIT (solo `strip`); las filas sin NIT van al log como ERROR | `_agrupar_por_empresa` (mismo criterio, filas sin NIT en silencio) | P:981-1006 · `inject:111-123` | Ninguno de los dos normaliza: `900111111` y `900111111-1` son dos empresas en ambos. Facturacion descarta en silencio las filas sin NIT y guarda la `Fecha Ingreso` (`inject:119-121`) | Mantener del ETL | Medio (mensajes; la fila P14 de la captura) |
| `_normalizar` / `_clave_ciudad`: NFD sin tildes y luego solo `A-Z0-9` | `CityAccountResolver._normalize` (NFD, conserva espacios y puntuación); `normalize_text_key` (unidecode, conserva espacios y `&`) | P:330-339 · `city_account_resolver.py:13-17`; `text_normalizer.py:34-40` | `"BOGOTA, D.C."` → `BOGOTADC` coincide exacto en el ETL; en Facturacion no coincide exacto y pasa al fuzzy. unidecode y NFD también difieren en símbolos: `"Nº 1"` → `N1` (ETL) frente a `NO 1` (`normalize_text_key`) | Mantener del ETL | Medio |

### 6.5 Fechas y zonas horarias

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| Factura **sin fechas**: ni `invoice_date`, ni vencimiento, ni `date_of_service`, ni `range_id` | `invoice_date`=hoy, `invoice_date_due`=hoy+30, `date_of_service`=último día del mes anterior, `range_id` por `Fecha Ingreso` | P:140-142, `1243-1250` · `inject:188-207`; `config.py:9-10`, `39-40`; `xmlrpc:399-413` | Cuatro campos que el ETL no envía. Además `find_date_range` compara como texto `"05/10/2026"` (dd/mm/aaaa del archivo, `inject:121`) con `date_start` en ISO, así que casi siempre cae en el respaldo "último rango" (`xmlrpc:408-411`) | Mantener del ETL (no enviar fechas) | **Alto** (todas las facturas) |
| Zona horaria: la guarda compara la medianoche **local** con `create_date`, que Odoo guarda en **UTC**; hora local en el log | No hay manejo de zona horaria (no aparece `timezone`/`tzinfo`/`utc` en `src/`); hora local por empresa | P:1259, `1787`, `1795`, `520` · `inject:82` | Con UTC−5, la guarda del ETL incluye los borradores creados desde las 19:00 locales del día anterior (lo hace a propósito: P:1253-1258). Facturacion no tiene guarda | Mantener del ETL (reproducir la comparación tal cual; E-10) | Medio (solo en corridas cerca de la medianoche) |

### 6.6 Redondeos y montos

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| Línea: `quantity` = número de pacientes con el examen (entero), `price_unit` = `list_price` del producto, sin redondeo | Igual | P:1148, `1180-1186` · `inject:140-147`, `166-172` | Ninguna en los montos: ninguno de los dos calcula importes; Odoo calcula el total | Reutilizar tal cual | Bajo |
| Valor del examen en el archivo: `_a_numero` (quita `$` y `,`, `float`; si falla, 1). Solo se usa en los libros de pendientes y de cuentas, y en el resumen con `format(..., ",.0f")` | El lector lo reduce a 1/`None` y se pierde el valor | P:964-976, `1331`, `1380`, `1895`, `1902`, `1906` · `excel_pre_invoice_reader.py:76-80` | Facturacion no conserva el valor. El ETL suma `float` (`"$12,500"` → `12500.0`) y redondea al mostrar con `,.0f` (mitad al par) | Mantener del ETL (solo en los libros; no llega a Odoo). Choca con la convención "no `float` en montos" de CLAUDE.md: decidir si se conserva `float` para la paridad | Medio (libros de pendientes y cuentas) |
| Precio desde la tarifa del cliente: `ACTUALIZAR_PRECIOS` → `update_puchase_line_prices` (JSON-RPC, 180 s) | No existe (la opción 6 lee tarifas de Odoo con otro fin, `xmlrpc:211`) | P:138, `557-613`, `1825-1835` · — | Apagado por defecto (`False`): las líneas suben con `list_price` | Mantener del ETL, apagado (o eliminar: E-05) | Bajo |

### 6.7 Lectura de archivos y armado de la factura

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| Filtro de archivos: `.xlsx`, sin `~$` ni `consolidado`, ordenados | Igual | P:1682-1687 · `excel_pre_invoice_reader.py:20-26` | Ninguna | Reutilizar tal cual | Bajo |
| `leer_prefactura` + `construir_filas`: columnas por nombre, examen = `^\d{6}(-\d{1,2})?$` en cualquier columna, se quita el sufijo literal `.0` | `ExcelPreInvoiceReader` | P:873-976 · `excel_pre_invoice_reader.py:11-91` | Facturacion toma 14 columnas fijas por posición (`:12`, `:69`), así que con la plantilla de 23 pierde `Paciente`, `N° Identificación`, `Observaciones Ingreso`; usa otra regex (`:11`); `rstrip(".0")` borra todos los `0` finales (`:61`), frente a `[:-2]` (P:907-908); no valida columnas obligatorias | Mantener del ETL | **Alto** (en la captura no se dispara, pero un encabezado `890200.0` se convertiría en `8902`) |
| Archivo ilegible o plantilla cambiada: copia a `verificar/` y fila ERROR al inicio del log | Solo `logger.error` y sigue | P:1740-1743, `1783-1788` · `excel_pre_invoice_reader.py:42-43` | Facturacion no lo reporta en el libro | Mantener del ETL | Medio (`901000005` en la captura) |
| Sin líneas → VERIFICAR; producto inexistente → pendientes "PRODUCTO NO ENCONTRADO"; cuadre de exámenes | Sin líneas → ERROR; producto inexistente → "Sin precio: […]" en el detalle; sin cuadre | P:1149-1170, `1211-1237` · `inject:149-156`, `182-186`, `213-214` | Estados y mensajes distintos | Mantener del ETL | Alto (estado de `901000006`) |
| Cabecera: `narration="Pre-factura automatica. Pacientes: N"` | `"Pre-factura automática. Pacientes: N"` | P:1248 · `inject:199` | **Tilde** en "automática": el valor enviado a Odoo difiere en todas las facturas | Mantener del ETL | **Alto** |
| Orden de las líneas: `sorted(conteo.items(), key=str)` | Orden de inserción del `dict` | P:1148 · `inject:151` | Distinto orden de `invoice_line_ids` | Mantener del ETL | Alto (las líneas se comparan en orden) |

### 6.8 Logging, salidas y manejo de errores

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| `logging.basicConfig`: `Salida/log_inyeccion.txt` + stdout, nivel INFO | `setup_logging` (`logs.log` rotativo de 10 MB, DEBUG) + `LoggerAdapter` con `user_msg` y `RichHandler` | P:515-525 · `src/shared/logging/config/logging_config.py:15-63`; `src/shared/logging/infrastructure/logging/logger_adapter.py:5-50` | Otro destino, otro formato y otros niveles. Según ADR-014, el detalle por fila no va a la consola | Descartar (los avisos de negocio del ETL, como cobro doble o nombre distinto, pasan a libros o al log técnico) | Medio: la paridad **no** debe comparar `log_inyeccion.txt` literalmente (está en `tests/paridad/esperado` solo como referencia) |
| `log_inyeccion.xlsx`: 10 columnas (+ Total, Precios), totales, colores | `ExcelLogGenerator`: 8 columnas | P:1571-1667 · `excel_log_generator.py:10`, `84-161` | Columnas y formato distintos. Cambiarlo rompe el golden `opcion8` | Mantener del ETL (generador propio del flujo nuevo) | Alto si se reutiliza |
| `pendientes_facturador.xlsx`, `cuentas_por_revisar.xlsx`, `facturas_creadas.csv` | `FindingsWriter` / `XlsxFindingsWriter` (un libro por tipo en `logs/<opcion>/<fecha>/`) | P:1403-1570, `1791-1792`, `1837-1841` · `src/shared/reporting/findings_writer.py:1-26`; `src/shared/reporting/xlsx_findings_writer.py:11-43` | Nombres, rutas y formato distintos (el ETL tiene hojas, colores y anchos propios) | Mantener del ETL (`FindingsWriter` puede sumarse aparte, según ADR-014) | Medio |
| Excepción en una empresa → ERROR (150 caracteres) y sigue | Igual | P:1818-1821 · `inject:218-220` | Facturacion además guarda la traza (`exc_info=True`) | Reutilizar tal cual | Bajo |
| Excepción fuera del bucle (p. ej. al conectar): el script termina | `safe_dispatch`: el menú sigue | (sin `try` global en P:1672-1911) · `main.py:106-120` | En ambos casos no se escriben libros de esa corrida | Reutilizar tal cual | Bajo |

### 6.9 Pruebas y punto de entrada

| Elemento en ETL | Equivalente en Facturacion | Archivos (ambos lados) | Diferencias de comportamiento | Decisión | Riesgo para la paridad |
|---|---|---|---|---|---|
| Sin pruebas | `OdooSimulado` del golden; `OdooParidad` lo extiende con `write` sin modificarlo | — · `tests/golden/_odoo_simulado.py`; `tests/paridad/capturar_referencia.py` | — | Reutilizar adaptando | Bajo |
| `python Pipeline.py` sobre `datos/Entrada/` | Opción 8 desconectada; el controller lee `pre-facturas/General sin factura` | P:87, `1672` · `main.py:50`, `89-91`; `inject_invoices_controller.py:19-20` | Otra carpeta de entrada y otra salida (`odoo-output/` frente a `datos/Salida/`) | Reutilizar adaptando (conectar la opción 8 al flujo nuevo) | Medio (qué carpeta: E-01) |

**Resumen.** Reutilizar tal cual: conexión, producto, impuesto, UdM, enlace, montos de línea, regla de no crear terceros,
manejo de excepciones. Reutilizar adaptando: validación de configuración, borrado del vencimiento, simulador, punto de
entrada. Descartar: carga del `.env` y logging. Todo lo demás (cliente, NIT, cuentas, fechas, lector, estados, narración,
orden de líneas, libros, guarda) es *Mantener del ETL*: es donde está casi todo el riesgo de paridad.

## 7. Diferencias de estilo y stack

| Aspecto | ETL-Avancys | Facturacion |
|---|---|---|
| Estructura | Un script de 1.911 líneas, funciones y estado global (`PENDIENTES`, `REVISAR`, `SIN_FACTURA`, cachés) | Hexagonal por módulo (ADR-001), inyección por constructor, controller como raíz de composición |
| Configuración | Constantes en el código que se editan cada mes (`YA_SUBIDAS`, bloqueos, mapas, `ACTUALIZAR_PRECIOS`) | Variables de entorno (`config.py`), BD |
| Datos | pandas (`dtype=str`), iteración por filas | Polars, operaciones vectorizadas |
| Excel de salida | openpyxl con formato manual (colores, anchos, hipervínculos) | xlsxwriter/openpyxl; `XlsxFindingsWriter` con Polars |
| Logging | `logging.basicConfig` (archivo `.txt` + stdout), mensajes con concatenación | `LoggerAdapter` con `user_msg`, Rich, `logs.log` rotativo, resumen único (ADR-014) |
| Errores | `try/except` amplio por empresa; `SystemExit` si falta configuración | Los use cases registran y siguen; `safe_dispatch` como último recurso |
| Pruebas | Ninguna | pytest con fakes (ADR-005), golden master, guardianes |
| `.env` | Parser propio, el entorno del sistema gana | python-dotenv con `override=True`, el `.env` gana |
| Odoo | `execute_kw` directo, sin timeout | Puerto `OdooConnectionRepository` + adaptador con timeout |
| Ejecución | `python Pipeline.py` sobre `datos/Entrada` | Menú Rich (`main.py`), rutas pedidas al usuario |
| Documentación | Comentarios extensos con el porqué y los incidentes de octubre-2026; README largo | ADRs, `TECHNICAL_DOCUMENTATION.md`, auditoría |

## 8. Cómo capturar salidas de referencia (`tests/paridad/esperado/`)

Restricciones: no modificar nada en ETL-Avancys (ni siquiera `datos/Salida/`, que el script escribe al
correr) y no tocar el Odoo de producción.

**Lo que hay que capturar.** La salida que importa no son los Excel sino lo que el ETL **envía a Odoo**:
las llamadas `execute_kw` de escritura (`account.move.create` con sus valores y `write` del vencimiento)
y, como salida secundaria, los cuatro libros y `facturas_creadas.csv` normalizados.

**Procedimiento propuesto (sin red, determinista):**
1. Copiar `Pipeline.py` **sin cambios** a un directorio temporal fuera de ambos repos
   (p. ej. el scratchpad), con una carpeta `datos/Entrada/` propia. `_buscar_datos` (`Pipeline.py:47-57`)
   resolverá `datos/` junto a la copia, así que no se escribe nada en ETL-Avancys. Fuera de los repos,
   `_cargar_env` no encuentra ningún `.env` (si la copia quedara bajo Facturacion leería su `.env` de producción).
2. Entradas: pre-facturas `.xlsx` generadas por la opción 7 real a partir de las entradas ficticias del golden
   (`tests/golden/entradas/`, escenario `opcion7`; el golden solo guarda su volcado JSON,
   `tests/golden/esperado/opcion7_prefacturas.json`), guardadas en `tests/paridad/entradas/`, más casos dirigidos (NIT sin tercero, ciudad fuera del mapa, sede EXTRAMURAL, SEDE 103 en otra
   ciudad, producto inexistente, examen repetido, plantilla sin `NIT`, fila sin NIT, empresa bloqueada).
   Nunca pre-facturas reales: traen datos de pacientes.
3. Un script arnés (en `tests/paridad/`) que define `ODOO_URL/DB/USER/API_KEY` con valores ficticios en
   `os.environ` (el entorno gana sobre el `.env`, `Pipeline.py:69`), sustituye `xmlrpc.client.ServerProxy`
   por `OdooSimulado` (`tests/golden/_odoo_simulado.py`) con partners, productos, impuestos, UdM y las
   cuentas analíticas necesarias y ejecuta la copia con `runpy.run_path(..., run_name="__main__")`.
   El reloj no se fija: la fecha/hora de ejecución se normaliza después (N1, N2 en `tests/paridad/LEEME.md`).
4. Guardar en `tests/paridad/esperado/`: el registro de escrituras (`create`/`write`, JSON canónico),
   `log_inyeccion.xlsx`, `pendientes_facturador.xlsx`, `cuentas_por_revisar.xlsx` volcados a JSON,
   `facturas_creadas.csv` y `log_inyeccion.txt`. La URL base es ficticia y fija, así que no hace falta normalizarla.

**Hecho el 2026-11-09:** `tests/paridad/` (`construir_entradas.py`, `capturar_referencia.py`, `normalizar.py`, `LEEME.md`).
5. Correrlo dos veces y comparar (el orden depende de `sorted` sobre nombres de archivo y de `dict`; no hay
   hash seed involucrado, pero se verifica).

**Validación contra el Odoo de pruebas (opcional, una vez):** para comprobar que el simulador reproduce a Odoo,
correr la misma copia con `ODOO_URL/DB/USER/API_KEY` apuntando a la instancia de pruebas
(`pruebas-soandesv14`, las variables `ODOO_TEST_*` del README) exportadas en el entorno, y leer después
los borradores creados (`account.move` + líneas) para compararlos con el registro del simulador. Crea
borradores reales en esa instancia: requiere autorización y una limpieza posterior (los IDs quedan en
`facturas_creadas.csv`).

## 9. Preguntas abiertas

| # | Pregunta |
|---|---|
| E-01 | ¿Qué carpetas de la opción 7 se inyectan? El controller de la opción 8 usa `pre-facturas/General sin factura`; el ETL lee lo que se copie a `datos/Entrada/` (hoy 315 archivos). ¿Todos los facturadores o solo GENERAL / General sin factura? |
| E-02 | Paridad del cliente: ¿se adopta la regla del ETL (`ref_num` exacto, ambiguo → VERIFICAR) aunque el resto de Facturacion use las 4 etapas con `vat` y `=like`? |
| E-03 | Anti-duplicados: ¿solo la guarda del ETL (mismo día), o además el log local de ADR-009 (cubre otros días, pero cambia el resultado frente al ETL)? ¿`YA_SUBIDAS` pasa a ser un archivo o tabla? |
| E-04 | ¿Dónde viven `NITS_BLOQUEADOS`, `EMPRESAS_BLOQUEADAS`, `CIUDAD_CUENTA`, `CIUDAD_CUENTA_ID`, `SEDE_CUENTA`, `RAMA_PRIORIDAD`: código, `.env`, BD o archivo de configuración? |
| E-05 | ¿Se conserva `ACTUALIZAR_PRECIOS` (JSON-RPC `update_puchase_line_prices`) o se elimina por estar siempre en `False`? |
| E-06 | ¿Cuál es la fuente de verdad: `Pipeline.py` de ETL-Avancys o el de Facturas-Avancys? ¿Pueden diferir hoy? |
| E-07 | ¿Hay acceso autorizado a la instancia de pruebas para validar el simulador y se permite crear borradores allí? |
| E-08 | El README dice "matching difuso de clientes con rapidfuzz + difflib" y "gravado (19%)", pero el código empareja cliente solo por `ref_num` exacto y "gravado" es solo la cuenta 42650 para `100006` (los impuestos son autorretenciones). ¿El código es la referencia? |
| E-09 | ¿Se reproducen tal cual comportamientos dudosos para la paridad: conteo doble en `cuentas_por_revisar` tras un reintento, `facturas_creadas.csv` truncado al iniciar, `narration` con filas en vez de pacientes únicos, nombre de empresa de la última fila? |
| E-10 | La guarda compara `create_date` (UTC) con la medianoche local: ¿se mantiene igual? |
| E-11 | ¿El timeout de 180 s del adaptador de Facturacion se acepta como diferencia (el ETL no tiene timeout en XML-RPC)? |
| E-12 | Los scripts auxiliares que el ETL menciona (`revisar_odoo.py`, `scripts/codigos_repetidos.py`, `ExportarTarifa.py`, `Tarifas.py`) viven en Facturas-Avancys: ¿quedan fuera del alcance? |
| E-13 | ¿Qué pasa con el código actual de `src/odooInjection` que difiere del ETL (lector de 14 columnas, `CityAccountResolver` con fallback, fechas, `create_client`)? ¿Se reemplaza o se conserva junto al nuevo flujo? |
