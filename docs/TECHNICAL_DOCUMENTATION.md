# Documentación Técnica — Sistema de Facturación SOANDES

> **Última actualización:** 2026-10-10 · **Rama de referencia:** `refactor/rates` · **Specs cubiertos:** 001–015
> Documento para desarrolladores. Para la operación diaria ver la [Guía de Usuario](USER_GUIDE.md).
> Las referencias `archivo:línea` apuntan al código vigente en esa fecha (incluye cambios aún no commiteados de specs 010–015).

## Índice

1. [Información general](#1-información-general)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Arquitectura](#3-arquitectura)
4. [Configuración del entorno](#4-configuración-del-entorno)
5. [Modelo de datos](#5-modelo-de-datos)
6. [Flujo de negocio](#6-flujo-de-negocio)
7. [Detalle por opción del menú](#7-detalle-por-opción-del-menú)
8. [Utilidades compartidas](#8-utilidades-compartidas)
9. [Logging y auditoría](#9-logging-y-auditoría)
10. [Testing](#10-testing)
11. [Proceso de desarrollo (SDD + TDD)](#11-proceso-de-desarrollo-sdd--tdd)
12. [Brechas conocidas y deuda técnica](#12-brechas-conocidas-y-deuda-técnica)

---

## 1. Información general

| Campo | Valor |
|---|---|
| Proyecto | Facturación SOANDES (`facture_new`) |
| Tipo | CLI puro (Rich), sin framework web |
| Lenguaje | Python 3.12+ |
| Base de datos | PostgreSQL (Supabase), SQLAlchemy 2.0, Alembic |
| ERP | Odoo 14 / Avancys vía XML-RPC |
| Arquitectura | Hexagonal (Ports & Adapters) por módulo |
| Entry point | `main.py` → menú → controller por opción |
| Tests | 834 en verde (pytest, fakes manuales) |

El sistema automatiza la facturación mensual de exámenes médicos ocupacionales para ~500 empresas clientes: valida NITs, carga catálogos y tarifas, asigna la tarifa a cada examen por paciente, separa pre-facturas por NIT/facturador y (cuando está habilitado) inyecta facturas borrador en Odoo.

## 2. Stack tecnológico

| Categoría | Tecnología | Uso |
|---|---|---|
| Datos | **Polars** (nunca pandas) | ETL de todos los libros Excel |
| Lectura Excel | **fastexcel / calamine** vía `ExcelLoader` | Lee todo como texto (`Utf8`) |
| Escritura Excel | **xlsxwriter** (CONSOLIDADO, normalizados) · Polars `write_excel` sobre xlsxwriter (libros de hallazgos) · **openpyxl** (pre-facturas, logs con formato) | openpyxl también se usa para **leer** el número de fila real de cada hoja en `MegaDataFrames` |
| BD | PostgreSQL, SQLAlchemy 2.0, psycopg2-binary, Alembic | |
| Scraping | **Playwright** (Firefox headless) contra `rues.org.co` | Opciones 1, 2, 5, 6 |
| ERP | `xmlrpc.client` → Odoo 14 | `res.partner`, `account.move`, `product.product`…; `account.base.rate`, `account.base.rate.line`, `res.city` (tarifas, solo lectura, opción 6) |
| Fuzzy | **RapidFuzz** + Unidecode | Ciudades, paquetes, facturadores, empresas |
| CLI | **Rich** | Menú, prompts, barras de progreso, mensajes al usuario (`USER_CONSOLE`), tabla resumen de la opción 6 |
| Tests | pytest 8.2.2 | Fakes manuales en `tests/fakes/` |
| Calidad | cspell, `.editorconfig` | No hay ruff/mypy/black/pre-commit |

## 3. Arquitectura

### 3.1 Estructura por módulo

```
src/<módulo>/
├── domain/
│   ├── entities/        # dataclasses puras
│   ├── repositories/    # puertos (ABC)
│   ├── services/        # lógica de dominio pura (p.ej. CupResolver, DuplicateCompanyDetector)
│   └── *.py             # objetos de dominio sueltos (p.ej. assign/domain/odoo_rate_index.py: OdooRateIndex)
├── application/
│   └── use_cases/       # orquestación; método execute()
└── infrastructure/
    ├── console/         # controllers Rich (*_controller.py) — arman dependencias
    ├── persistence/     # adaptadores Sa* (SQLAlchemy), lectores Excel
    ├── odoo/            # XML-RPC (odooInjection)
    ├── scrapers/        # Playwright (scrapping)
    └── reporting/       # generadores de logs y libros de hallazgos (p.ej. XlsxPhaseFindingsReporter)
```

Reglas (constitución v1.1.0):

- Los repositorios son **ABC en `domain/repositories/`**, implementados en `infrastructure/persistence/` con prefijo `Sa*`, y **devuelven `list[dict]`**, nunca objetos ORM.
- `application/` no importa SQLAlchemy.
- Los tests usan **fakes manuales** (`tests/fakes/Fake*Repo`) que implementan la misma ABC.

### 3.2 Módulos

| Módulo | Responsabilidad | Opción |
|---|---|---|
| `scrapping` | Validación de NITs: Odoo (fuente de verdad) → BD local (respaldo) → RUES; sincroniza la BD local con Odoo | 1 |
| `billers` | Facturadores y vínculo empresa↔facturador | 2 |
| `dataProcessing` | Normalización de paquetes/proveedores/especiales + corrección de CUPs | 3 |
| `rates` | Importación de tarifas a BD | 4 |
| `company` | Empresas, vínculo empresa↔paquete, duplicados, i-medical, TIAN | 5, 10 |
| `assign` | Asignación de tarifas (Odoo especial → base, luego cascada local) → `CONSOLIDADO.xlsx` + libros por fase; faltantes | 6, 9 |
| `preInvoice` | Split del CONSOLIDADO por facturador/NIT | 7 |
| `odooInjection` | Inyección en Odoo + `XmlRpcOdooRepository` (reutilizado por 1, 2, 5, 6): búsqueda de clientes por `ref_num` → `vat` y lectura de tarifas para la opción 6 | 8 (deshabilitada) |
| `package`, `provider`, `special`, `city`, `cup`, `activity` | Catálogos | — |
| `shared` | BD, Excel, consola, utilidades, logging, reporting (`FindingsWriter`), config | — |

### 3.3 Entry point

`main.py`:

- `console_app()` (l.103-130) pinta el menú y pide `Seleccione una opción` (por defecto `0`).
- `dispatch_option()` (l.39-83) despacha al controller.
- `safe_dispatch()` (l.86-100) captura cualquier excepción no controlada, la loguea con `user_msg` y vuelve al menú (spec 007 RF-09).
- Todos los controllers reciben `tech_logger` (`LoggerAdapter`). La opción 6 lo envuelve en `TechOnlyLogger`, que descarta `user_msg`.

## 4. Configuración del entorno

### 4.1 Instalación

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install firefox
alembic upgrade head
python main.py
```

### 4.2 Variables de entorno (`.env`, plantilla en `.env.example`)

**Base de datos.** La aplicación usa `src/shared/database/database.py:13-29`:

| Variable | Defecto | Nota |
|---|---|---|
| `SUPABASE_DB_USER` / `SUPABASE_DB_PASSWORD` | — | Password con `quote_plus` |
| `SUPABASE_DB_HOST` | — | |
| `SUPABASE_DB_PORT` | `5432` | |
| `SUPABASE_DB_NAME` | `postgres` | |

La URL es `postgresql+psycopg2://…?sslmode=require` con `pool_pre_ping=True`. La app **ignora `DATABASE_URL`**. Alembic (`migrations/env.py:15-24`), en cambio, sí usa `DATABASE_URL` si existe; si no, arma la URL con `SUPABASE_DB_*`, puerto por defecto **6543** y sin `sslmode`.

**Rutas y negocio:**

| Variable | Defecto | Uso |
|---|---|---|
| `DIRECTORY` | `.` (`src/shared/config.py`, `get_paths_config`) | Dónde quedan `data.json` y `logs.log` |
| `BOOK_ROUTE`, `BOOK_NAME` | **sin defecto** | Libro de entrada de la opción 1 |
| `DAY_INITIAL`, `DAY_FINAL` | **sin defecto** (obligatorias) | Opción 6: pide libro de facturas si `día < DAY_INITIAL` o `día > DAY_FINAL` |
| `TIAN_NIT` | **sin defecto** a propósito (`get_tian_config`) | NIT al que se redirigen las empresas TIAN; si falta, se omite el tratamiento |

**Scraping / matching (opción 1):**

| Variable | Defecto |
|---|---|
| `COMPANY_NAME_MATCH_THRESHOLD` | 90 |
| `LOCAL_NAME_LOOKUP` | true |
| `RUES_NAME_LOOKUP_LIMIT` | 200 |
| `RUES_SCRAPER_CONCURRENCY` | 1 (máx. 5) |
| `RUES_RESULT_TIMEOUT_MS` | 10000 |
| `RUES_REQUEST_DELAY_MS` | 1000 |

**Odoo** (`src/odooInjection/config.py:13-41`, `get_odoo_config`):

| Variable | Defecto |
|---|---|
| `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY` | `""` (sin usuario/API key se omite Odoo) |
| `ODOO_DIARIO_ID` | 47 |
| `ODOO_CUENTA_INGRESOS_EXCLUIDOS` / `_GRAVADOS` | 42653 / 42650 |
| `ODOO_CUENTA_RECEIVABLE` / `_PAYABLE` | 40921 / 41977 |
| `ODOO_PRODUCTOS_GRAVADOS` | `"100006"` (CSV) |
| `ODOO_TAX_AUTORRETENCION_RENTA` | `AUTORRETENCION IMPUESTO RENTA 2%` |
| `ODOO_TAX_AUTORRETENCION_COMPRAS` | `AUTORRETENCION COMPRA IMPUESTO RENTA 2%` |
| `ODOO_UOM` | `Unidades` |
| `ODOO_FECHA_VENCIMIENTO_DIAS` | 30 |

> ⚠️ Una variable numérica **definida pero vacía** (como viene en `.env.example`, p.ej. `ODOO_DIARIO_ID=` o `DAY_INITIAL=`) hace fallar `int("")`. Hay que dejarla con valor o comentarla.

## 5. Modelo de datos

### 5.1 Tablas (`src/shared/database/models.py`)

Todas las tablas tienen `created_at` y `updated_at` (`now()`).

| Tabla | Columnas / restricciones |
|---|---|
| `type_activities` | `id` PK · `name` String(10) UNIQUE, CHECK IN ('INTRA','EXTRA') |
| `cups` | `id` PK · `code` String(9) UNIQUE · `name` String(255) UNIQUE |
| `cities`, `billers`, `packages`, `providers`, `specials` | `id` PK · `name` String(255) UNIQUE |
| `companies` | `id` PK · `nit` String(12) UNIQUE · `name` · `verified_at` |
| `companies_billers` | PK (`biller_id`, `company_id`) · `company_id` FK UNIQUE → **una empresa, un facturador** |
| `companies_packages` | PK (`company_id`, `package_id`, `model`) · UNIQUE(`company_id`) → **una empresa, un paquete**; `package_id` es polimórfico según `model` |
| `rates` | PK compuesta (`rateable_id`, `city_id`, `cup_id`, `activity_id`, `rateable_type`) · `rate` BigInteger |
| `imedical` | `nit_error` PK · `name` · `nit_success` · `name_error` (nullable) · `deleted_at` |
| `tian` | `nit_error` PK · `name` · `deleted_at` |

**Polimorfismo.** `rates.rateable_type` y `companies_packages.model` valen `Package`, `Provider` o `Special`, y apuntan a `packages`, `providers` o `specials`. Toda lógica que toque tarifas debe considerar los tres tipos.

```
companies ─1:1─ companies_billers ─N:1─ billers
    │
    └─1:1─ companies_packages ──(model)──► packages | providers | specials
                                                   ▲
rates (rateable_type, rateable_id) ────────────────┘
rates.city_id → cities · rates.cup_id → cups · rates.activity_id → type_activities
imedical / tian: tablas de corrección indexadas por nit_error (sin FK)
```

### 5.2 Diferencias ORM ↔ migraciones

- Las migraciones crean `deleted_at` en todas las tablas; el ORM solo lo declara en `imedical` y `tian`.
- Las FK de `rates` y `companies_billers.biller_id` existen solo en BD, no en el ORM.
- Las tablas RBAC (`roles`, `permissions`, `role_permissions`, `users`) existen en BD sin modelo ORM ni uso.

### 5.3 Migraciones (`migrations/versions/`, en orden de `down_revision`)

| # | Revisión | Cambio |
|---|---|---|
| 1 | `1f61750cbea8` | initial (vacía) |
| 2–14 | `0d916af0d32e` … `bc1d152a1ddb` | Creación de `type_activities`, `cups`, `imedical`, `billers`, `cities`, `packages`, `providers`, `specials`, `tian`, `companies`, `companies_packages`, `companies_billers`, `rates` |
| 15 | `f60655fefc7f` | Tablas RBAC |
| 16 | `a1c2d3e4f5a6` | `companies.verified_at` + backfill |
| 17 | `b3f8c1d92e07` | Borra 2 NIT con DV inválido (spec 006 RF-11) |
| 18 | `afa85e5b3c40` | `imedical.name_error` + elimina UNIQUE `nit_success` (spec 008) — *aún sin commitear* |

> Los comentarios `Revises:` de `6f0ab654aacd` y `bc1d152a1ddb` no coinciden con su `down_revision` real. Vale el `down_revision`.

### 5.4 Modelos de Odoo que se leen (solo lectura)

Todo acceso a Odoo desde las opciones 1, 2, 5 y 6 usa `search_read` o `read`; ningún flujo activo escribe en Odoo.

| Modelo | Campos usados | Nota |
|---|---|---|
| `res.partner` | `ref_num` (*Número de identificación*: el **NIT**), `verification_code` (DV), `vat` (casi siempre vacío), `name`, `rate_base_special_id` (*Tarifa especial*), `rate_base_id` (*Tarifa base*) | La búsqueda por NIT usa `ref_num` y cae a `vat` (spec 012) |
| `account.base.rate` | `name`, `state`, `start_date`, `finish_date` | Tarifa. El estado **no** se valida; la vigencia solo se reporta: una tarifa con `finish_date` anterior a hoy se asigna y queda en `odoo_tarifa_vencida.xlsx` (spec 020) |
| `account.base.rate.line` | `base_rate_id`, `city_id` (→ `res.city`), `product_id` (`default_code` = CUP), `price_unit`, `intra` (bool) | Línea de precio por ciudad, CUP y actividad |
| `product.product` | `default_code` | Se lee en un solo `read` para obtener el CUP de cada línea |

## 6. Flujo de negocio

Flujo secuencial y stateful. Cada opción consume la salida de la anterior y no hay orquestador:

```
 Libro NITs ──► [1] Web Scrapping ──► data.json + companies (caché) + empresas_no_encontradas.xlsx + logs/web_scrapping/<fecha>/
 Libro gestores ─► [2] Facturadores ──► billers, companies_billers + logs/facturadores/<fecha>/
 Libro tarifas ─► [3] Tratamiento ──► facturacion_normalizada.xlsx + novedades_cups.xlsx
                       │
                       ▼
                  [4] Cargar Tarifas ──► cities, packages, providers, specials, rates + logs/cargar_tarifas/<fecha>/
 Libro empresas ─► [5] Registrar Empresas ──► companies, companies_packages (+ no_vinculadas) + logs/registrar_empresas/<fecha>/
 Odoo (tarifas especial/base) ──┐
 Consolidado de atenciones ─► [6] Asignar Tarifas ──► CONSOLIDADO.xlsx (colores por fase) + logs/asignar_tarifas/<fecha>/
                                                           │
                       ┌───────────────────────────────────┼───────────────────┐
                       ▼                                   ▼                   ▼
             [7] Pre Facturas ──► pre-facturas/…   [9] Faltantes     (revisión manual)
                       │
                       ▼
             [8] Inyección Odoo (DESHABILITADA en main.py)
 [10] Detectar duplicados: lectura de companies en cualquier momento
```

**Contrato crítico:** el formato del `CONSOLIDADO.xlsx` (nombres de columna, hoja `Consolidado` y colores de relleno) lo consume `preInvoice`. Cambiarlo rompe la opción 7. `split_by_nit` solo copia los rellenos de su lista blanca `_PHASE_COLORS_6`: un color nuevo en la opción 6 debe agregarse allí (la spec 010, RF-16, agregó `E2EFDA`).

## 7. Detalle por opción del menú

### 7.1 Opción 1 — Web Scrapping (`src/scrapping`)

- **Cadena:** `execute_web_scrapping` (`infrastructure/console/import_rues_nits.py:58`) → `SearchNitsWithOdooFallbackUseCase.execute` (`application/use_cases/search_nits_with_odoo_fallback_use_case.py:87`) → `SearchNitsUseCase`.
- **Entrada:** `BOOK_ROUTE/BOOK_NAME`, hoja `nits`, columnas `nits` (obligatoria) y `empresa` (opcional; sin ella solo se busca por NIT).
- **Puertos:** `NitScraperRepository`, `NitCacheRepository`.
- **Adaptadores:** `RuesPlaywrightScraper` (`infrastructure/scrapers/rues_selenium_scraper.py:28`; usa Playwright aunque el archivo diga selenium), `SaCompanyNitCacheRepository` (índices en memoria por NIT/nombre sobre `companies`), `XmlRpcOdooRepository`.
- **Cascada de 8 pasos, con Odoo como fuente de verdad** (spec 016; use case l.105-310). Cada paso recibe solo lo que quedó pendiente del anterior. Odoo se consulta **siempre**, también para los NIT que ya están en la BD local; la BD local es el respaldo:

| Paso | Fuente | Criterio |
|---|---|---|
| 1 | Odoo | NIT en batch en 4 etapas (`_find_partners_by_document`, spec 012): `ref_num in` → `ref_num =like 'nit%'` (espacio final o DV pegado) → `vat in` → `vat =like 'nit%'`. Lotes de 500 (`in`) y 50 (`=like`); cada etapa consulta solo los pendientes; se acepta una fila si `normalize_nit` del campo coincide; gana el menor `id`. Una sola llamada para todos los NIT, conocidos o no |
| 2 | Odoo | Nombre (`ilike` sin sufijo societario, límite 10) + validación fuzzy. El documento devuelto sale de `ref_num`, con `vat` sin DV como respaldo (`_document_of`) |
| 3 | BD local | NIT normalizado (respaldo si Odoo no lo tiene o no está disponible) |
| 4 | BD local | Nombre normalizado exacto |
| 5 | RUES | NIT (9 primeros dígitos). Antes de scrapear se usa la caché `rues_cache` (entradas de `data.json` cuya fuente es RUES); solo el resto se consulta |
| 6 | RUES | Nombre (hasta `RUES_NAME_LOOKUP_LIMIT`) + validación fuzzy |
| 7 | — | `is_company=False` → pendiente de revisión manual |
| 8 | BD local ← Odoo | Sincronización (ver abajo) |

- **Odoo no disponible** (falla `connect` o falla la consulta en lote): se continúa con BD local y RUES, la consola muestra *Odoo no disponible: se validó con la BD local y RUES.* y no se escribe nada en la BD local basado en Odoo (`odoo_available = False`).
- **Sincronización de la BD local con Odoo (paso 8, spec 016):** para cada empresa que resolvió Odoo se compara con la BD local en una sola lectura en memoria y se guarda en **un único `save_many`** (que reutiliza el upsert por NIT de `SaCompanyRepository.save_batch`, ADR-012):
  - no existe en la BD local → **Agregada**;
  - existe con otra razón social (comparación normalizada) → **Actualizada**;
  - la razón social de Odoo ya la usa otra empresa con otro NIT → no se actualiza, `conflict = "Nombre duplicado en BD local con otro NIT"` y **No actualizada: nombre duplicado en BD local**;
  - iguales → no se escribe nada.

  Antes de escribir, `SaCompanyNitCacheRepository.save_many` deduplica por NIT normalizado (gana el resultado de fuente Odoo; spec 017), porque un NIT repetido en el mismo `INSERT … ON CONFLICT DO UPDATE` hace fallar todo el lote. Si el guardado falla por un error técnico, `save_many` lanza `NitCacheSaveError`: ningún NIT queda con `conflict`, cada resultado lleva `save_error`, la acción es **No actualizada: error al guardar** y la consola muestra un único mensaje con el número de empresas afectadas. `SaCompanyRepository.save_batch` devuelve `None` ante una excepción y `[]` cuando no había nada que guardar o todo se filtró por nombre. `empresas_no_encontradas.xlsx` solo lista NIT que no existen en Odoo; conflicto y error de guardado no se escriben allí.

  El detalle queda en `use_case.local_updates`, que se publica como libro `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción). Odoo nunca se modifica.
- **`data.json` como caché de RUES:** `load_rues_cache(path)` (`src/scrapping/infrastructure/persistence/rues_json_cache.py`) lee `data.json` y conserva solo las entradas cuyo `source` empieza por `RUES`. Las de Odoo, las de BD local y las del formato anterior (sin `source`) se ignoran, así que Odoo se vuelve a consultar. Un archivo ausente o ilegible da una caché vacía. Los use cases la reciben como argumento (`rues_cache`), no leen archivos.
- **Fuzzy:** `CompanyNameMatcher` sobre `RapidFuzzBiller.fuzz_property`: `token_sort_ratio`, si no alcanza `partial_ratio`, y acepta con score ≥ 90. `_names_differ` usa el mismo matcher para no reportar novedades falsas (spec 003).
- **Salidas:** `DIRECTORY/data.json` (lista de `NitResult` de la corrida), sincroniza `companies` con Odoo y persiste los positivos nuevos de RUES, escribe `logs/web_scrapping/<AAAA-MM-DD_HHMM>/bd_local_actualizada.xlsx` (con resumen en consola) y `logs/empresas_no_encontradas.xlsx` (acumulativo). Es la **única** opción que pasa al libro todos los resultados, así que es la única que retira un NIT cuando queda resuelto sin novedades.
- **Dato de Odoo (spec 012):** de los 57 clientes que solo tienen `vat`, 54 son duplicados de un partner original con el mismo NIT en `ref_num`, creados entre el 2026-05-07 y el 2026-06-02 (probablemente por `create_client`, que solo llena `vat`). Con la prioridad por `ref_num` se elige el partner original. Se recomienda que el administrador de Odoo los fusione o archive.

### 7.2 Opción 2 — Facturadores (`src/billers`)

- **Cadena:** `import_billers` (`infrastructure/console/import_billers_controller.py:60`, arma dependencias en `_build_use_case` l.32 e inyecta el `logger`) → `ImportBillersFromExcel.execute` (`application/use_cases/import_billers_from_excel.py:53`).
- **Entrada:** columnas `GESTOR`, `NIT`, `EMPRESA`.
- **Algoritmo:**
  1. `_process_billers`: toma los GESTOR únicos y los empareja por fuzzy (90) con `billers`; hace upsert por `name`.
  2. `_process_companies`:
     - Envía **todos** los NIT del Excel, conocidos o no, a `RUESNitService.search(nits, rues_cache=…)`: Odoo primero (spec 016). `data.json` solo aporta la caché de RUES (`load_rues_cache`, inyectada como `rues_cache_loader`) y se reescribe con los resultados de la corrida.
     - Hace `save_batch` con el nombre que dio la búsqueda (el de Odoo tiene prioridad).
     - Vincula GESTOR→biller por fuzzy; si no encuentra el NIT, cae a un match **exacto** por nombre.
     - Deduplica por `company_id` y hace upsert en `companies_billers` con `ON CONFLICT(company_id)`: gana el último. Repetir la empresa con el **mismo** facturador no es conflicto (spec 015).
- **Hallazgos** (`logs/facturadores/<AAAA-MM-DD_HHMM>/`, specs 011 y 015):
  - `empresa_no_encontrada` y `facturador_no_encontrado` (columnas NIT, Facturador).
  - `vinculacion_duplicada` (NIT, Empresa, Facturador descartado, Facturador vigente), una fila por reemplazo.
  - `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción): empresas agregadas o corregidas en la BD local con datos de Odoo (spec 016).
  - Al terminar, la consola muestra el resumen de `summarize_findings`.

### 7.3 Opción 3 — Tratamiento de Información (`src/dataProcessing`)

- **Cadena:** `import_information` → `NormalizeInformationFromExcel` → `NormalizePackage` / `NormalizeProvider` / `NormalizeSpecial` → `CupColumnValidator` → servicio de dominio `CupResolver` (`domain/services/cup_resolver.py:36`).
- **Entrada:** hojas `Paquetes`, `Proveedores` y todas las que empiezan por `TarifasEspeciales` (se concatenan). Columnas `CONTRATO`, `CIUDAD`, `CUP`, `EXAMEN`, `INTRA O EXTRA`, `VALOR`.
- **Normalización:** limpia espacios. En Proveedores y Especiales unifica el `CONTRATO` por slug (unidecode + solo letras).
- **Cascada de corrección de CUP** (spec 005):

| Fase | Regla | ¿Aplica? |
|---|---|---|
| F0 | CUP inválido y VALOR con forma de código válido → intercambio | Sí |
| F1 | `EXAMEN` normalizado == `cups.name` (claves en colisión excluidas) | Sí |
| F2 | Co-ocurrencia inequívoca del mismo EXAMEN en la hoja | Sí (si hay >1 candidato: "CUPs en conflicto") |
| F3 | Homologación de sufijo `904704-1` → `904704` | Sí |
| F4 | Fuzzy ≥ 90 | **Solo sugiere** |

- **Salidas:** `<dir>/facturacion_normalizada.xlsx` (`ExcelExporter`; parte las hojas de más de 1.048.575 filas) y `logs/novedades_cups.xlsx` (se reemplaza en cada corrida).
- **BD:** solo lee `cups`.

### 7.4 Opción 4 — Cargar Tarifas (`src/rates`)

- **Cadena:** `import_rates` (`infrastructure/console/import_rates_controller.py:50-57`; dependencias en `_build_use_case` l.32-47) → `ImportRatesFromExcel.execute` (`application/use_cases/import_rates_from_excel.py:86`).
- **Entrada:** hojas `Paquetes`, `Proveedores`, `TarifasEspeciales*` y `Ciudades`. Columnas `CIUDAD`, `CONTRATO`, `CUP`, `VALOR`, `INTRA O EXTRA`.
- **Reclasificación de `CONTRATO`** (`src/shared/utils/mega_dataframes.py`, `total_dataframe` l.55+). Antes, `_load_tagged` (l.34) agrega a cada fila `_HOJA` y `_FILA` (número de fila real en Excel, leído con openpyxl; en secuencia si no se puede leer, p. ej. `.xls`). Esas columnas no se persisten:
  - Lo que empieza por TARIFA o PAQUETE → paquete.
  - Lo que contiene PROVEEDOR → proveedor.
  - El resto → especial.
- **Resolución de nombres:**
  - Exacto, o fuzzy ≥ **95**.
  - Los especiales con match fuzzy distinto se **renombran** en sitio (`_resolve_names_with_renames`, p.ej. `ALQUERIA 2025` → `ALQUERIA 2026`) y conservan el `id`.
  - Las ciudades usan alias fuzzy ≥ **90** (`BOGOTA` → `BOGOTA D.C`).
- **Persistencia:** lotes de 1000.
  - `_save_deduped` deduplica por la PK compuesta (gana la última fila). PostgreSQL rechaza `ON CONFLICT DO UPDATE` si hay claves repetidas en el mismo batch.
  - Upsert en `SaRatesRepository.save_batch` (`sa_rates_repository.py:128`).
- **Errores por fila:** contrato, ciudad, CUP o actividad inexistentes, o valor vacío → se registra en el log técnico, se salta la fila y queda en `logs/cargar_tarifas/<AAAA-MM-DD_HHMM>/` (spec 011):
  - Libros: `contrato_no_existe`, `ciudad_no_existe`, `cup_no_existe`, `actividad_invalida`, `tarifa_vacia`.
  - Columnas: Hoja, Fila, CONTRATO, CIUDAD, CUP, INTRA O EXTRA, VALOR (el VALOR original, antes de limpiarlo). Deduplicado por (tipo, hoja, fila).
  - La consola muestra un único resumen. Como la opción crea antes los contratos y ciudades del Excel, en la práctica aparecen sobre todo `cup_no_existe`, `actividad_invalida` y `tarifa_vacia`.

### 7.5 Opción 5 — Registrar Empresas - Paquetes (`src/company`)

- **Cadena:** `import_companies` (`infrastructure/console/import_companies_rates_controller.py:81-95`; sesión cerrada en `finally`) → `ImportCompaniesFromExcel.execute` (`application/use_cases/import_companies_from_excel.py:67`).
- **Entrada:** columnas `NIT`, `RAZON SOCIAL`, `PAQUETE`.
- **Fase 1 `_progress_companies`:**
  - Normaliza con `normalize_document`: NIT o cédula, validación de DV (ver §8). Un documento acotado con DV inválido va a `documento_acotado` (Documento original, Documento acotado).
  - Envía **todos** los documentos del Excel, también los que ya existen en `companies`, a `RUESNitService.search(docs, rues_cache=…)`: Odoo primero (spec 016). `data.json` solo aporta la caché de RUES y se reescribe con los resultados de la corrida. La razón social de las empresas conocidas la corrige el buscador (libro `bd_local_actualizada`).
  - Hace `save_batch` solo de las empresas **nuevas** (*Empresas creadas* cuenta solo esas). Los no encontrados se **agregan** a `empresas_no_encontradas.xlsx` (esta opción no retira los resueltos).
- **Fase 2 `_progress_companies_to_packages`:**
  - Arma un catálogo unificado de packages, providers y specials (esquema `id/name/model`). Si un origen está vacío lo advierte; si están los tres vacíos, envía todo a no vinculadas.
  - Resuelve `PAQUETE` por fuzzy ≥ **95**.
  - Deduplica por `company_id` (gana la última fila). Cada repetición va a `paquetes_en_conflicto` (Documento, Paquete descartado, Paquete vigente); un paquete no resuelto va a `paquete_no_encontrado` (Documento, Razón social, Paquete).
  - Hace upsert `ON CONFLICT(company_id)`.
- **Salidas:** `logs/empresas_no_vinculadas.xlsx` (se reemplaza), `logs/empresas_no_encontradas.xlsx` (acumulativo; solo la opción 1 retira NITs resueltos) y `logs/registrar_empresas/<AAAA-MM-DD_HHMM>/`. El resumen final en consola es *Empresas creadas … Filas sin vincular … Hallazgos en …* (o *Sin hallazgos.*).

### 7.6 Opción 6 — Asignar Tarifas (`src/assign`)

- **Cadena:** `assign_rates(logger, with_invoices)` (`infrastructure/console/assigned_rates_controller.py:95`) → `AssignRatesFromExcel.execute` (`application/use_cases/assigned_rates.py:219-313`).
- **Dependencias:**
  - Repositorios: `SaBillerRepository`, `SaCompanyRepository`, `SaBillerCompanyRepository`, `SaPackageRepository`, `SaProviderRepository`, `SaSpecialRepository`, `SaCityRepository`, `SaActivityRepository`, `SaRatesRepository`, `SaCupRepository`, `XmlRpcOdooRepository`, `SaImedicalRepository`, `SaTianRepository`.
  - Generadores de logs: `NotFoundCompaniesLogGenerator`, `TianCompaniesLogGenerator`; hallazgos por fase: `XlsxPhaseFindingsReporter` (`findings_reporter`).
  - Logger: el controller envuelve el `tech_logger` en `TechOnlyLogger` (l.120), así que ninguna dependencia escribe en la consola.
  - Al terminar, el controller imprime `render_summary(AssignRatesResult)` (l.79): una tabla Rich con las celdas por origen del precio.

#### Pipeline

| # | Paso | Notas |
|---|---|---|
| 1 | `_connect_odoo` | Si falla, sigue solo con BD local y RUES, y sin tarifas Odoo (todo por cascada local; aviso en el resumen) |
| 2 | `_build_lookups` | |
| 3 | `_capture_raw_nit` | `_NIT_RAW` = dígitos sin truncar |
| 4 | **`_apply_imedical`** | Corrige NIT erróneos conocidos usando el NIT crudo (l.463-500) |
| 5 | `_normalize_nit` | 9 dígitos |
| 6 | `_match_companies` | Cascada Odoo NIT → Odoo nombre → BD NIT → BD nombre → RUES NIT → RUES nombre → `[NOVEDAD]`. Incluye el bloqueo y el auto-registro i-medical y la unificación del nombre canónico por NIT (l.700-741) |
| 7 | `_normalize_nit`, `_normalize_columns` | Fechas dd/mm/yyyy con *smart swap* (`_parse_fecha`, l.830); sufijos societarios; actividad `INTRAMURAL`→`INTRA` (l.792) |
| 8 | **`_apply_tian`** | Va después de normalizar porque `pl_normalize_name` borra los paréntesis (l.882-976) |
| 9 | `_normalize_city` | Fuzzy ≥ 90 contra `cities` |
| 10 | **`_load_odoo_rates`** (l.172) | `find_partner_rates_batch(nits)` → `find_rate_lines(ids, CUPs)` → `OdooRateIndex`. Arma los hallazgos `empresas_odoo`. Ante un error, aviso en `logs.log` e índice vacío |
| 11 | `_assign_facturador` | Left join por NIT; sin facturador → `GENERAL` |
| 12 | `_assign_paquete` (l.1035) | Copia el paquete local a `_PAQUETE_LOCAL` (sin paquete → `PAQUETE C 2025`); `PAQUETE` = tarifa especial Odoo › tarifa base Odoo › paquete local |
| 13 | `_assign_rates` | Primero `_resolve_odoo_cells` (l.1094), luego cascada local (abajo) |
| 14 | `_validate_empresa` | Corrige nombres según BD; excluye los NIT TIAN y los resueltos por Odoo |
| 15 | `_drop_internal_columns` (quita `_NIT_RAW` y `_PAQUETE_LOCAL`), `_enrich_with_invoices`, `_order_columns`, export, `_write_legend` (l.315), `_publish_findings` (l.329) → `AssignRatesResult` | |

#### Tarifas de Odoo (spec 010)

- **Orden:** Tarifa especial → Tarifa base → las 6 fases locales → `1`.
- **Índice:** `OdooRateIndex` (`src/assign/domain/odoo_rate_index.py`). Clave `(tarifa, normalize_text_key(ciudad), CUP, intra)`; INTRA ↔ `intra=True`, EXTRA ↔ `intra=False`. Los precios ≤ 0 se ignoran y, ante claves repetidas, gana la primera línea.
- **Ciudad:** solo por nombre normalizado exacto (sin fuzzy). No se valida el estado de la tarifa; la vigencia vencida se asigna igual y se reporta (spec 020, RF-04).
- **Consulta:** `find_rate_lines` lee las líneas en lotes de 50 tarifas, filtradas por los CUP del Excel, y lee `default_code` en un solo `read`.
- **Color:** una celda resuelta por Odoo **no lleva color**.
- **PAQUETE:** nombre de la tarifa especial, si no la base, si no el paquete local. La cascada local sigue leyendo `_PAQUETE_LOCAL`.
- **Odoo no disponible** o falla la consulta: todo va por la cascada local, no se genera `empresas_odoo` y el resumen muestra el aviso en amarillo.

#### Cascada de tarifas local (`_assign_rates`, l.1117-1480)

- **Clave:** `(rateable_id, city_id, cup_id, activity_id, rateable_type)`.
- **Columnas CUP:** las que tienen encabezado de dígitos y guiones (l.1133). Una celda con valor `1` significa "examen realizado, tarifar".
- **Recolección de claves** (l.1139-1206): solo para las celdas que Odoo no resolvió. Por celda se agregan la clave propia, la de `PAQUETE C 2025` y, si el CUP tiene sufijo `-N`, la del CUP base en `PAQUETE C 2025`. El paquete local se lee de `_PAQUETE_LOCAL`.
- **Consulta:** una sola `find_batch` (`sa_rates_repository.py:31-63`, `tuple_ IN` por bloques).

> **El código implementa 6 fases locales, no 7.** Los comentarios del código numeran "Phase 3…7" porque las fases 1 y 2 internas son recolección y consulta. Aquí se usa la numeración de la hoja `Leyenda`. Antes de las 6 fases locales van las 2 etapas de Odoo (especial y base), sin color.

| Fase | Busca | Fuente | Color | Código |
|---|---|---|---|---|
| Odoo especial | `rate_base_special_id` + ciudad + CUP + intra | `OdooRateIndex` | sin color | l.1094-1113 |
| Odoo base | `rate_base_id` + ciudad + CUP + intra | `OdooRateIndex` | sin color | l.1094-1113 |
| 1 | Paquete propio + ciudad + CUP + actividad | `rates_cache` | `#E2EFDA` verde claro (`_COLOR_LOCAL_OWN`, l.91) | l.1257-1262 |
| 2 | `PAQUETE C 2025` + ciudad + CUP + actividad | `rates_cache` | `#FFF2CC` dorado suave | l.1263-1274 |
| 3 | Cualquier rateable + ciudad + CUP + actividad | `find_any_rate` | `#F4B183` naranja | l.1280-1318 |
| 4 | CUP base en `PAQUETE C 2025` + ciudad + actividad | `rates_cache` | `#BDD7EE` azul acero claro | l.1320-1355 |
| 5 | Cualquier rateable + ciudad + CUP base + actividad | `find_any_rate` | `#9DC3E6` azul medio | l.1357-1413 |
| 6 | Cualquier rateable + cualquier ciudad + CUP + actividad | `find_rate_by_cup_activity` | `#D5A6E6` púrpura | l.1415-1450 |
| — | Sin resolver | — | sin color, valor `1` → `sin_resolver.xlsx` | l.1452 |

Detalles:

- `_COLOR_PHASE7` (`FFB6C1`) se eliminó de `assigned_rates.py` (spec 010); persiste en `split_by_nit.py:50,63` (lista blanca y Leyenda de las pre-facturas).
- La homologación (fases 4 y 5) solo aplica a CUP con guion cuyo código base existe en `cups`.
- Si no existe `PAQUETE C 2025`, las fases 2 y 4 se omiten.
- Si el paquete, la ciudad o la actividad de una fila no existen en BD, la cascada local no procesa la fila: solo quedan con precio las celdas que haya resuelto Odoo y el resto en `1`.
- Las fases 3, 5 y 6 **no son deterministas**: la consulta no tiene `ORDER BY` y gana la primera fila que devuelva la BD.
- `Total` = `sum_horizontal` de las columnas CUP.
- La hoja `Leyenda` se crea si hubo al menos una celda coloreada o resuelta por Odoo. Filas: *Sin color — Tarifa Odoo (especial/base)* y las 6 fases (`_PHASE_LEGEND`, l.93).

#### Hallazgos y resumen (spec 010)

- `PHASE_FINDING_KEYS` (l.82) → `logs/asignar_tarifas/<AAAA-MM-DD_HHMM>/`: `fase_01_paquete_propio_local`, `fase_02_paquete_c_2025`, `fase_03_cualquier_paquete`, `fase_04_cup_base_paquete_c`, `fase_05_cup_base_cualquier_paquete`, `fase_06_cualquier_ciudad` y `sin_resolver`.
  - Columnas: NIT, Empresa, Paciente, N° Identificación, Ciudad, TIPO DE ACTIVIDAD, CUP, Precio asignado, Origen. Una fila por (paciente, CUP).
- `empresas_odoo`: NIT, Empresa, Motivo (*No encontrada en Odoo* / *Sin tarifa especial ni base*).
- Las celdas resueltas por Odoo no generan libro y no se escriben libros vacíos.
- `execute` devuelve `AssignRatesResult(counts, findings_dir, odoo_available)`; el controller lo muestra con `render_summary`: filas *Tarifa Odoo (especial/base)*, *Fase 1…6*, *Sin resolver (valor 1)*, y como pie la carpeta de hallazgos o *Sin hallazgos*, más el aviso amarillo si Odoo no estuvo disponible.

#### Tratamientos especiales (spec 008)

**i-medical** (tabla `imedical`):

1. **Corrección:** si el NIT crudo de la fila está en `imedical.nit_error`, se reemplaza por `nit_success`. Solo se cargan las correcciones reales: se ignoran las idénticas y las que ya se resuelven al truncar a 9 dígitos (l.398-417).
2. **Bloqueo:** un NIT corregido por i-medical no se vuelve a cambiar por coincidencia de nombre en Odoo, BD o RUES. Queda el log `[NOVEDAD] imedical bloqueó cambio de NIT`.
3. **Auto-registro:** se guarda una corrección nueva cuando se cumplen todas estas condiciones (detección l.597-602; guardado l.743):
   - La columna `Base` contiene `IMEDICAL`.
   - Odoo, buscando por nombre, devuelve otro NIT.
   - La similitud del nombre es ≥ 90.
   - El NIT no estaba registrado.

   El guardado es `save_batch` con upsert por `nit_error`.

**TIAN** (tabla `tian` + `TIAN_NIT`):

- Las filas cuyo NIT (final o crudo) está en `tian` se facturan al NIT `TIAN_NIT`.
- El nombre queda `"<razón social>(TIAN)"`, sin duplicar el sufijo.
- Heredan el facturador, el paquete y las tarifas de TIAN, incluida la tarifa Odoo del `TIAN_NIT` (`_load_odoo_rates` corre después de `_apply_tian`).
- Se abortan sin error (con aviso) si falta `TIAN_NIT`, si TIAN no existe en `companies` o si no tiene paquete.
- Se escribe `logs/empresas_tian.xlsx` (se reemplaza en cada corrida). En la opción 6 los avisos van solo a `logs.log` (`TechOnlyLogger`).

**Unificación de nombre por NIT:** si un mismo NIT llega con varios nombres, se toma el canónico con prioridad Odoo > BD > primer visto. Nunca se compara por similitud.

#### Libro de facturas (`with_invoices=True`)

- Requiere `N° Identificación` y `# FACTURA`; si falta alguna, `ValueError`.
- Las facturas múltiples de una misma identificación se concatenan con `", "`. Se cruzan por left join con el consolidado y llenan la columna `FACTURAS`.

### 7.7 Opción 7 — Generar Pre Facturas (`src/preInvoice`)

- **Cadena:** `generate_pre_invoices` (`infrastructure/console/pre_invoice_controller.py`) → `SplitByNit(logger, cup_repo, RichProgress()).execute(...)` (`application/use_cases/split_by_nit.py`).
- **Rutas fijas:** entrada `CONSOLIDADO.xlsx` (hoja `Consolidado`), salida `pre-facturas/`.
- **Algoritmo:**
  1. Carga con openpyxl, sin `read_only`, para leer los rellenos de fase. Solo copia los de la lista blanca `_PHASE_COLORS_6` (incluye `E2EFDA` desde la spec 010 y aún `FFB6C1`). La `Leyenda` de las pre-facturas dice *Sin color — Tarifa Odoo (especial/base)* y las fases 1–6, más una fila obsoleta *Fase 7*.
  2. Ordena las columnas: las 23 de `FIXED_COLUMNS` (l.14-38) y luego las CUP (`^\d+(-\d+)?$`).
  3. Determina la carpeta por fila (l.139-151):
     - FACTURADOR vacío → `SIN_FACTURADOR`.
     - `GENERAL` con alguna factura que empieza por `SET` → `GENERAL`.
     - `GENERAL` sin esa factura → `General sin factura`.
     - Otro facturador → carpeta con su nombre.
  4. **Proceso 1:** `pre-facturas/<carpeta>/pre_factura_<NIT>_<Empresa>.xlsx`.
     - Hojas `BASE GENERAL` y `Leyenda`.
     - Fila 1 = nombre del CUP según el catálogo, fila 2 = encabezados, panel congelado en A3.
     - Solo las columnas CUP con algún valor para ese NIT.
  5. **Proceso 2:** `pre-facturas/NITs_consolidado.xlsx`, una hoja por empresa (31 caracteres, sufijo `_n` si se repite).
- **Spec 009:** `Fecha Ingreso` se conserva en todas las carpetas, incluida `General sin factura`.
- Si un NIT falla, se loguea y se continúa con el siguiente.

### 7.8 Opción 8 — Inyección en Odoo (`src/odooInjection`) — **DESHABILITADA**

`main.py:69-71` solo imprime el mensaje; la llamada `inject_invoices(logger)` está comentada y no hay otro entry point. El módulo está completo y testeado:

- **Cadena:** `inject_invoices` (`inject_invoices_controller.py:23-52`) → `InjectInvoicesToOdoo.execute` (`application/use_cases/inject_invoices_to_odoo.py:34-99`).
- **Dependencias:** `ExcelPreInvoiceReader`, `XmlRpcOdooRepository`, `CityAccountResolver` y `ExcelLogGenerator`.
- **Flujo:**
  1. **Lectura:** los `.xlsx` de `pre-facturas/General sin factura` (fila 2 = encabezado; 14 columnas fijas; CUP desde la columna 15).
  2. **Anti-duplicados (ADR-009):** excluye los NIT con estado `OK` en `odoo-output/log_inyeccion.xlsx`.
  3. **Cliente (ADR-010):** `find_client` delega en `find_clients_batch([nit])`: `ref_num` exacto → `ref_num =like 'NIT%'` → `vat` exacto → `vat =like 'NIT%'` (spec 012). Si no aparece, el use case llama `find_client_by_name` (`name ilike` sin sufijo societario). Si tampoco → **VERIFICAR**. `create_client` existe en el repositorio (solo llena `vat`) pero **no se invoca**.
  4. **Líneas:**
     - Cuenta los exámenes por (CUP, cuenta analítica). La cuenta analítica sale de la ciudad: exacta o WRatio ≥ 80; si no hay, `AA8638`.
     - Producto por `default_code`.
     - Cuenta de ingresos gravados o excluidos según `ODOO_PRODUCTOS_GRAVADOS`.
     - Impuestos de autorretención y UoM.
  5. **`account.move`:** `out_invoice`, `draft`, `invoice_date` = hoy, vencimiento a +N días, `journal_id`, `date_of_service` = último día del mes anterior, `range_id`.
  6. **Log:** `odoo-output/log_inyeccion.xlsx`. Estados OK, VERIFICAR o ERROR; el histórico se fusiona y gana el resultado más reciente.

### 7.9 Opción 9 — Generar Faltantes (`src/assign`)

- **Cadena:** `generate_missing_rates` (`missing_rates_controller.py`) → `missing_rates.py`.
- **Entrada:** normalmente `CONSOLIDADO.xlsx`. Columnas `NIT`, `Empresa`, `PAQUETE`, `Ciudad`, `TIPO DE ACTIVIDAD`, `Base` y las columnas CUP.
- **Salida:** `<dir>/faltantes.xlsx`, hoja `Faltantes`. Tiene una fila por cada celda CUP que siga en `"1"`, deduplicada por NIT+PAQUETE+Ciudad+Actividad+CUP+Base.

### 7.10 Opción 10 — Detectar Empresas Duplicadas (`src/company`)

- **Cadena:** `detect_duplicate_companies` → `DetectDuplicateCompanies` (`application/use_cases/detect_duplicate_companies.py`) → servicio de dominio `DuplicateCompanyDetector` (`domain/services/duplicate_company_detector.py`).
- **Regla A:** misma clave de nombre (sin puntuación ni espacios) con NIT distinto.
- **Regla B:** un NIT es igual al otro más un dígito (DV pegado) y `token_sort_ratio` de los nombres ≥ **85**.
- Se descartó el fuzzy general porque daba ~14 falsos positivos por cada duplicado real.
- Es de solo lectura. Salida: `logs/empresas_duplicadas.xlsx` (se reemplaza en cada corrida).

## 8. Utilidades compartidas

| Utilidad | Ubicación | Comportamiento |
|---|---|---|
| `ExcelLoader` | `src/shared/excel/excel_loader.py` | `load`, `load_sheet`, `load_sheets_by_prefix`. Calamine, todo `Utf8`, encabezados con `strip`. Descarta las filas totalmente vacías |
| `MegaDataFrames` | `src/shared/utils/mega_dataframes.py` | Reclasifica `CONTRATO` (opción 4) y etiqueta cada fila con `_HOJA`/`_FILA` de origen (`_load_tagged`) |
| `ExcelExporter` | `src/shared/excel/excel_exporter.py` | Exporta varias hojas, parte las de más de 1.048.575 filas, `sanitize_sheet_name` (31 caracteres) |
| `normalize_nit` | `src/shared/utils/text_normalizer.py:48` | Solo dígitos, **primeros 9** |
| `normalize_document` | `src/shared/utils/document_normalizer.py` | NIT si tiene 9–10 dígitos y empieza por 8/9 (el de 10 se acota y se valida su DV DIAN); en otro caso **CEDULA íntegra**. Devuelve `DocumentResult(value, kind, original, truncated, dv_valid)` |
| `calculate_dian_dv` | idem | Pesos DIAN 3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71 |
| `normalize_company_name` / `normalize_text_key` | `text_normalizer.py` | unidecode, mayúsculas, `[A-Z&Ñ0-9\s]`; versiones Polars `pl_normalize_*` |
| `CompanyNameNormalizer` | `company_name_normalizer.py` | Quita sufijos SAS/SA/BIC/LTDA/ESP/EU y agrupa por fuzzy (85) |
| `RapidFuzzBiller` | `rapidfuzz_biller.py` | `fuzz_property(name, catalog, threshold=90)`: `token_sort_ratio`, luego `partial_ratio`. `similarity(a, b)` |
| `get_paths_config` / `get_tian_config` | `src/shared/config.py` | `DIRECTORY` (por defecto `.`), `TIAN_NIT` (sin defecto) |
| Consola | `src/shared/console/` | `file_input` (valida `.xlsx`/`.xls` existente), `sheet_input`, `file_output` (valida directorio), `RichProgress` (usa `USER_CONSOLE`), `user_console.py` (`USER_CONSOLE`, `build_user_console_handler`) |
| `FindingsWriter` / `summarize_findings` | `src/shared/reporting/findings_writer.py` | Puerto `write(books, columns) -> Path \| None`; resumen *Sin hallazgos.* o *Hallazgos en <carpeta>: tipo=n, …* |
| `XlsxFindingsWriter` | `src/shared/reporting/xlsx_findings_writer.py` | Un libro por tipo en `<base>/<AAAA-MM-DD_HHMM>/`; no crea carpeta si no hay filas |
| `TechOnlyLogger` | `src/shared/logging/infrastructure/logging/tech_only_logger.py` | Decorador de `LoggerAdapter` que descarta `user_msg` |
| `OdooRateIndex` | `src/assign/domain/odoo_rate_index.py` | Índice de precios de Odoo (ver §7.6) |

> **NIT vs cédula.** El NIT se acota a 9 dígitos sin DV y la cédula se conserva entera. El DV no clasifica el documento. Usar `normalize_document` donde pueda llegar una cédula y `normalize_nit` donde el dato es NIT con certeza.

## 9. Logging y auditoría

**Salida al usuario (ADR-014, reemplaza a ADR-008 y ADR-011):**

| Canal | Destino | Formato |
|---|---|---|
| `tech_logger` | `<DIRECTORY>/logs.log` | `RotatingFileHandler`, DEBUG, 10 MB × 5 |
| `user_logger` | Consola Rich (`USER_CONSOLE`) | `RichHandler`, INFO; color por nivel. La misma consola la usa `RichProgress`, así los mensajes salen por encima de la barra sin romperla |
| Hallazgos por fila | `logs/<opcion>/<AAAA-MM-DD_HHMM>/<tipo>.xlsx` | `FindingsWriter` / `XlsxFindingsWriter` (Polars + xlsxwriter); un libro por tipo, sin libros vacíos. La opción 6 usa `PhaseFindingsReporter` / `XlsxPhaseFindingsReporter`, que envuelve `XlsxFindingsWriter` (`logs/asignar_tarifas`) |

- `setup_logging()` (`src/shared/logging/config/logging_config.py`) carga `spec/user_logger.yaml`, lo valida (si falla, usa una configuración de respaldo solo con consola) e instala `root_logger_guard`; el handler de consola del usuario se construye con una factory (`src/shared/console/user_console.py`). Ese guard bloquea `addHandler`/`setLevel` sobre el logger raíz y es el origen de los ~882 warnings de pytest (2026-10-10).
- `LoggerAdapter` (`infrastructure/logging/logger_adapter.py`) acepta `user_msg=` en todos los niveles: el mensaje técnico va al logger propio y `user_msg` se reenvía a `user_logger`, que lo muestra en la consola. `user_msg` es solo para resúmenes y errores puntuales; el detalle por fila de un hallazgo va a su libro. `TechOnlyLogger` descarta `user_msg` en los flujos con salida propia (opción 6): por eso los avisos de i-medical, TIAN, empresas no encontradas y fechas quedan solo en `logs.log` o en sus libros, y la consola muestra solo la tabla de `render_summary`.

```python
logger.error(f"Fallo leyendo {path}: {e}", exc_info=True,
             user_msg="No se pudo procesar el archivo.")

# Hallazgos por fila: el use case los acumula y los publica al terminar
folder = self.findings_writer.write(self._findings, COLUMNS)   # None si no hay filas
self.logger.info("Resumen", user_msg=summarize_findings(self._findings, folder))
```

**Logs de negocio** (los consume el usuario):

| Archivo | Opción | Política |
|---|---|---|
| `logs/empresas_no_encontradas.xlsx` | 1, 5, 6 | Acumulativo. Solo la opción 1 retira un NIT resuelto; las opciones 5 y 6 solo agregan los no encontrados |
| `logs/novedades_cups.xlsx` | 3 | Se reemplaza |
| `logs/empresas_no_vinculadas.xlsx` | 5 | Se reemplaza |
| `logs/empresas_tian.xlsx` | 6 | Se reemplaza |
| `logs/empresas_duplicadas.xlsx` | 10 | Se reemplaza |
| `odoo-output/log_inyeccion.xlsx` | 8 | Acumulativo (anti-duplicados) |
| `logs/<opcion>/<AAAA-MM-DD_HHMM>/*.xlsx` | 1, 2, 4, 5, 6 | Nuevo en cada ejecución; dos corridas en el mismo minuto comparten carpeta y la segunda reemplaza los libros con el mismo nombre |

**Hallazgos por opción:**

| Opción | Carpeta | Libros (columnas) |
|---|---|---|
| 1 | `logs/web_scrapping/` | `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción) |
| 2 | `logs/facturadores/` | `empresa_no_encontrada`, `facturador_no_encontrado` (NIT, Facturador); `vinculacion_duplicada` (NIT, Empresa, Facturador descartado, Facturador vigente); `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción) |
| 4 | `logs/cargar_tarifas/` | `contrato_no_existe`, `ciudad_no_existe`, `cup_no_existe`, `actividad_invalida`, `tarifa_vacia` (Hoja, Fila, CONTRATO, CIUDAD, CUP, INTRA O EXTRA, VALOR) |
| 5 | `logs/registrar_empresas/` | `documento_acotado` (Documento original, Documento acotado); `paquetes_en_conflicto` (Documento, Paquete descartado, Paquete vigente); `paquete_no_encontrado` (Documento, Razón social, Paquete); `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción) |
| 6 | `logs/asignar_tarifas/` | `fase_01`…`fase_06`, `sin_resolver` (NIT, Empresa, Paciente, N° Identificación, Ciudad, TIPO DE ACTIVIDAD, CUP, Precio asignado, Origen); `empresas_odoo` (NIT, Empresa, Motivo) |

## 10. Testing

```bash
pytest                                   # 834 passed (2026-10-10)
pytest tests/assign/ -v                  # un módulo
pytest tests/assign/test_assigned_rates.py::TestX::test_y -v
```

- `pytest.ini`: `testpaths = tests`. `tests/conftest.py` agrega la raíz del proyecto a `sys.path` y define fixtures con los fakes.
- **Fakes manuales** (`tests/fakes/`, 28 archivos): repos (`fake_*_repo`), `fake_logger`, `fake_progress`, `fake_fuzz`, `fake_nit_scraper`, `fake_nit_service`, `fake_odoo_repo` (con `partner_rates`, `rate_lines`, `calls` y `write_attempts`), generadores de logs (`fake_*_log_generator`), `fake_findings_writer` y `fake_phase_findings_reporter`.
- Matiz: los tests de adaptadores `Sa*` usan `unittest.mock` para la `Session`. La regla de "sin mocks" aplica a los use cases.
- `FakeLogger` **no captura `user_msg`**. Un AC sobre "el mensaje al usuario" necesita un doble local que lo registre; si no, pasa en verde sin verificarse nada. Para hallazgos, se aserta sobre `FakeFindingsWriter.books` / `FakePhaseFindingsReporter`.
- Los tests de `XmlRpcOdooRepository` sobrescriben `_execute`: `tests/odooInjection/test_find_clients_by_ref_num.py` trae un simulador de Odoo en memoria que evalúa dominios (`in`, `=`, `=like`, `ilike`, OR) y falla ante cualquier método que no sea de lectura.
- **Guardianes de la suite:**
  - `tests/test_no_duplicate_test_names.py` (spec 013): falla si un módulo o una clase define dos `test_*` con el mismo nombre.
  - `tests/test_dead_code_removed.py` (spec 014): el código eliminado no vuelve ni se referencia.
  - `tests/docs/`: verifica el contenido de README, `docs/` y las reglas del proyecto (p. ej. que no se describa como vigente el antiguo registro Excel de usuario).

| Carpeta | Tests (2026-10-10) |
|---|---|
| assign | 172 |
| scrapping | 151 |
| shared | 121 |
| company | 109 |
| odooInjection | 75 |
| dataProcessing | 65 |
| rates | 39 |
| billers | 37 |
| preInvoice | 22 |
| catálogos y `test_main_dispatch.py` | 25 |
| `tests/docs` | 6 |
| `test_dead_code_removed.py` | 7 |
| `test_no_duplicate_test_names.py` | 5 |

## 11. Proceso de desarrollo (SDD + TDD)

- Todo cambio de comportamiento sigue el ciclo **spec → plan → task → execute → verify** en `specs/NNN_nombre/{spec,plan,task,verify}.md`, bajo `specs/constitution.md` (v1.1.0).
- Un spec con preguntas abiertas no avanza a plan.
- Las tasks declaran un contrato de alcance (Crear / Modificar / PROHIBIDO tocar) y el test que debe fallar primero.
- `verify.md` cruza cada AC con su test y audita el drift de alcance.

| Spec | Tema |
|---|---|
| 001 | Prompts claros en la opción 6 |
| 002 | Cascada NIT→nombre en la opción 1 |
| 003 | Falsos positivos de "nombre corregido" y vínculo empresa↔facturador |
| 004 | Detección de empresas duplicadas (opción 10) |
| 005 | Corrección de CUPs en la opción 3 |
| 006 | Normalización NIT/cédula y dedup de vínculos (opción 5) |
| 007 | Robustez de la opción 5, `safe_dispatch`, `DIRECTORY` único |
| 008 | i-medical, TIAN y unificación de nombres (opción 6) |
| 009 | Conservar Fecha Ingreso en "General sin factura" |
| 010 | Tarifas de Odoo (especial → base) en la opción 6, libros por fase y resumen en consola |
| 011 | Salida al usuario por consola Rich y libros de hallazgos por ejecución (ADR-014) |
| 012 | Búsqueda de clientes en Odoo por `ref_num` con respaldo en `vat` |
| 013 | Tests con nombre duplicado + guardián |
| 014 | Eliminación de código muerto (repositorios MySQL/PG de paquetes, `update_package`, scraper de datos.gov.co, `iLogger`) |
| 015 | Vinculación duplicada en la opción 2: prevalece la última, libro con descartado y vigente |
| 016 | Odoo como fuente de verdad en la validación de empresas (opciones 1, 2 y 5): Odoo primero, BD local como respaldo sincronizada con Odoo, `data.json` solo caché de RUES |

Decisiones arquitectónicas: [docs/adr/](adr/README.md) · Diagramas: [docs/c4-diagrams.md](c4-diagrams.md).

## 12. Brechas conocidas y deuda técnica

Lo que sigue se detectó al documentar y **no se corrigió**. Cada punto es candidato a su propio spec.

| # | Área | Hallazgo | Ubicación |
|---|---|---|---|
| 1 | Código | **Resuelto en `assign` (spec 010).** Queda `FFB6C1` / *Fase 7* en la lista blanca y la Leyenda de las pre-facturas | `split_by_nit.py:50,63` |
| 2 | Opción 8 | Inyección deshabilitada (llamada comentada, sin import) | `main.py:69-71` |
| 3 | Opción 1 | **Resuelto (spec 014):** el scraper `datos_gov_scraper.py` (no se usaba y no implementaba `search_by_name`) se eliminó. La cascada real es Odoo → BD local → RUES (spec 016) | — |
| 4 | Opción 2 | El fallback de vínculo por nombre sigue siendo exacto (spec 003 RF-02 pedía fuzzy; tasks sin marcar) | `import_billers_from_excel.py:167-173` |
| 5 | Opciones 2 y 5 | **Cambió (spec 016):** `data.json` se reescribe con los resultados de la corrida (también los de RUES que vinieron de la caché), pero pierde los de NIT que no estaban en el Excel de esa corrida | `import_billers_from_excel.py`, `import_companies_from_excel.py` |
| 6 | Opción 3 | `str.replace("[\s]{2,}", "")` reemplaza solo la primera ocurrencia y pega palabras | normalizadores `dataProcessing` |
| 7 | Opción 3 | `VERIFIED=True` significa que el CUP sigue **sin** existir (semántica invertida) | `cup_column_validator.py:197` |
| 8 | Opción 3 | `VALOR` "5.000" → 5 | `_is_success` |
| 9 | Opción 5 | `SaCompanyNitCacheRepository.save_many` usa `normalize_nit`, y una cédula de 10 o más dígitos puede quedar truncada | `sa_company_nit_cache_repository.py:64-67` |
| 10 | Opción 5 | Un paquete no encontrado va a `paquete_no_encontrado.xlsx` (spec 011), pero sigue sin entrar a `empresas_no_vinculadas.xlsx` | `import_companies_from_excel.py:322-331` |
| 11 | Opción 6 | Las fases comodín (3, 5, 6) no son deterministas (sin `ORDER BY`) | `sa_rates_repository.py:89,122` |
| 12 | Opción 6 | `DAY_INITIAL`/`DAY_FINAL` vacíos → `int()` falla (lo captura `safe_dispatch`) | `main.py:59-65` |
| 13 | Opción 7 | El mensaje de consolidado faltante usa `print` y muestra `[red]` literal | `pre_invoice_controller.py:19-21` |
| 14 | BD | La app ignora `DATABASE_URL`; Alembic la usa (puertos por defecto 5432 vs 6543) | `database.py`, `migrations/env.py` |
| 15 | BD | Los controllers de las opciones 4 y 10 no cierran la sesión | spec 007, no-objetivos |
| 16 | Arquitectura | `SaBillerRepository` / `SaBillerCompanyRepository` no heredan su ABC; `rates` no tiene ABC | `src/billers`, `src/rates` |
| 17 | Opción 6 | `TechOnlyLogger` oculta en consola los avisos de i-medical, TIAN (incluido *No se definió TIAN_NIT*), empresas no encontradas y fechas: solo quedan en `logs.log` | `assigned_rates_controller.py:120` |
| 18 | Opción 6 | `render_summary` se imprime con un `Console()` nuevo y no con `USER_CONSOLE` | `assigned_rates_controller.py:156` |
| 19 | Opción 6 | La ciudad de Odoo se compara por nombre normalizado exacto y no se valida el estado ni la vigencia de la tarifa | `odoo_rate_index.py` |
| 20 | Opción 5 | `paquetes_en_conflicto` se registra aunque la empresa se repita con el **mismo** paquete (la regla "mismo valor no es conflicto" de la spec 015 solo se aplicó a la opción 2) | `import_companies_from_excel.py:305-320` |
| 21 | Odoo | `create_client` escribe solo `vat`, no `ref_num` (no se invoca) | `xmlrpc_odoo_repository.py:238-249` |
| 22 | Datos Odoo | 54 partners duplicados creados solo con `vat` (2026-05-07 a 2026-06-02); el administrador de Odoo debe fusionarlos o archivarlos | Odoo, `res.partner` |
| 23 | `empresas_no_encontradas` | Las opciones 5 y 6 solo agregan no encontrados y nunca retiran los resueltos; solo la opción 1 limpia el libro | `import_companies_from_excel.py`, `assigned_rates.py:698` |
| 24 | Opción 6 | La opción 6 valida las empresas Odoo-primero pero no sincroniza la BD local con Odoo (sí lo hacen las opciones 1, 2 y 5, spec 016) | `assigned_rates.py` |
