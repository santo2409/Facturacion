# Diagramas C4 - Sistema de Facturación SOANDES

Diagramas arquitectónicos según el modelo C4 (Context, Container, Component, Code), más diagramas de flujo de las reglas de negocio clave.
Notación: [Mermaid](https://mermaid.js.org/), que se renderiza en GitHub/GitLab y VS Code.

> **Última actualización:** 2026-10-10 (specs 001–015). Texto complementario en la [Documentación Técnica](TECHNICAL_DOCUMENTATION.md).

---

## Nivel 1: Diagrama de Contexto

El sistema y sus interacciones con actores y sistemas externos.

```mermaid
C4Context
    title Sistema de Facturación SOANDES - Diagrama de Contexto

    Person(facturador, "Facturador", "Ejecuta el ciclo de facturación mensual desde el menú CLI")
    Person(coordinador, "Coordinador", "Revisa CONSOLIDADO, pre-facturas y reportes de novedades")

    System(facturacion, "Sistema de Facturación SOANDES", "CLI que valida empresas, carga tarifas, asigna tarifas por examen y genera CONSOLIDADO y pre-facturas")

    System_Ext(rues, "RUES", "Registro Único Empresarial y Social: validación pública de NIT y razón social")
    System_Ext(odoo, "Odoo 14 / Avancys", "ERP: maestro de clientes (res.partner, NIT en ref_num), tarifas oficiales por empresa (account.base.rate) y destino de facturas")
    SystemDb_Ext(db, "PostgreSQL (Supabase)", "Catálogos, empresas, tarifas, correcciones i-medical / TIAN")
    System_Ext(excel, "Libros Excel", "Entradas (atenciones, tarifas, empresas, gestores) y salidas (CONSOLIDADO, pre-facturas, logs)")

    Rel(facturador, facturacion, "Ejecuta opciones 1-10", "Terminal")
    Rel(facturador, excel, "Prepara libros de entrada")
    Rel(coordinador, excel, "Revisa salidas y logs de novedades")
    Rel(facturacion, rues, "Consulta NIT y nombre", "HTTPS / Playwright")
    Rel(facturacion, odoo, "Valida clientes por NIT (ref_num, respaldo vat) y nombre; lee tarifas especial/base. Solo lectura; inyección deshabilitada", "XML-RPC / HTTPS")
    Rel(facturacion, db, "Lee y escribe", "SQL / TLS")
    Rel(facturacion, excel, "Lee entradas y genera salidas", "fastexcel / xlsxwriter / openpyxl")
```

---

## Nivel 2: Diagrama de Contenedores

Las piezas técnicas principales del sistema.

```mermaid
C4Container
    title Sistema de Facturación SOANDES - Diagrama de Contenedores

    Person(usuario, "Facturador / Coordinador")

    System_Boundary(sistema, "Sistema de Facturación (proceso Python único)") {
        Container(cli, "Aplicación CLI", "Python 3.12 / Rich", "main.py: menú, dispatch_option y safe_dispatch (contiene excepciones por opción)")
        Container(core, "Casos de uso", "Python / Polars", "application/use_cases por módulo: importación, normalización, asignación, split, inyección")
        Container(domain, "Dominio", "dataclasses + ABC", "Entidades, puertos (repositorios ABC) y servicios puros: CupResolver, DuplicateCompanyDetector, OdooRateIndex")
        Container(persistence, "Adaptadores de persistencia", "SQLAlchemy 2.0 / Alembic", "Repositorios Sa* que devuelven list[dict]")
        Container(scraper, "Scraper RUES", "Playwright (Firefox headless)", "RuesPlaywrightScraper: búsqueda por NIT y por nombre")
        Container(odoo_client, "Cliente Odoo", "xmlrpc.client", "XmlRpcOdooRepository: clientes (búsqueda por documento en 4 etapas), tarifas especial/base (account.base.rate.line), productos, impuestos, account.move")
        Container(excel_io, "E/S Excel", "fastexcel / xlsxwriter / openpyxl", "ExcelLoader, ExcelExporter y generadores de reportes")
        Container(logging_sys, "Logging y salida al usuario", "logging + RichHandler", "tech_logger → logs.log · user_logger → consola Rich · hallazgos → libros por ejecución")
    }

    ContainerDb(db, "PostgreSQL", "Supabase", "companies, billers, packages, providers, specials, rates, cups, cities, type_activities, imedical, tian")
    System_Ext(rues, "RUES", "www.rues.org.co")
    System_Ext(odoo, "Odoo 14 / Avancys", "soandesv14")
    System_Ext(fs, "Sistema de archivos", "Libros de entrada, CONSOLIDADO.xlsx, pre-facturas/, logs/, data.json")

    Rel(usuario, cli, "Elige opción", "Terminal")
    Rel(cli, core, "Construye dependencias e invoca execute()")
    Rel(core, domain, "Usa entidades, puertos y servicios")
    Rel(persistence, domain, "Implementa puertos")
    Rel(core, excel_io, "Lee/escribe DataFrames")
    Rel(core, scraper, "Valida empresas")
    Rel(core, odoo_client, "Valida clientes, lee tarifas / inyecta")
    Rel(core, logging_sys, "logger.x(..., user_msg=...)")
    Rel(persistence, db, "SQL", "psycopg2, sslmode=require")
    Rel(scraper, rues, "HTTPS")
    Rel(odoo_client, odoo, "XML-RPC: search_read / read; escritura solo en op. 8 (deshabilitada)", "HTTPS")
    Rel(excel_io, fs, ".xlsx")
    Rel(logging_sys, fs, "logs.log, logs/<opcion>/<fecha>/*.xlsx")
```

---

## Nivel 3: Diagrama de Componentes

Módulos de negocio, la opción del menú que atiende cada uno y sus dependencias compartidas.

```mermaid
C4Component
    title Módulos de negocio - Diagrama de Componentes

    Container_Boundary(core, "Módulos (src/<módulo>)") {
        Component(scrapping, "scrapping (op. 1)", "SearchNitsWithOdooFallbackUseCase", "Cascada Odoo (fuente de verdad) → BD local (respaldo) → RUES por NIT y por nombre; sincroniza la BD local con Odoo. data.json (solo caché de RUES) + empresas_no_encontradas.xlsx + bd_local_actualizada")
        Component(billers, "billers (op. 2)", "ImportBillersFromExcel", "Facturadores por fuzzy (90) y vínculo empresa↔facturador (1:1); duplicado: gana el último. Hallazgos en logs/facturadores")
        Component(dataProcessing, "dataProcessing (op. 3)", "NormalizeInformationFromExcel + CupResolver", "Normaliza contratos y corrige CUPs (F0-F4). novedades_cups.xlsx")
        Component(rates, "rates (op. 4)", "ImportRatesFromExcel", "Reclasifica contratos, fuzzy de ciudad (90) y nombres (95), rename de especiales, dedup + upsert. Hallazgos con Hoja/Fila en logs/cargar_tarifas")
        Component(company, "company (op. 5, 10)", "ImportCompaniesFromExcel, DetectDuplicateCompanies", "normalize_document NIT/cédula, vínculo empresa↔paquete (1:1), duplicados; repos imedical/tian. Hallazgos en logs/registrar_empresas")
        Component(assign, "assign (op. 6, 9)", "AssignRatesFromExcel, MissingRates", "i-medical, cascada de empresas, TIAN, tarifa Odoo (especial → base) y cascada local de 6 fases → CONSOLIDADO.xlsx; libros por fase en logs/asignar_tarifas; faltantes.xlsx")
        Component(preInvoice, "preInvoice (op. 7)", "SplitByNit", "Split por facturador/NIT conservando colores de fase (lista blanca, incluye E2EFDA)")
        Component(odooInjection, "odooInjection (op. 8, deshabilitada)", "InjectInvoicesToOdoo", "Anti-duplicados, VERIFICAR en vez de crear, account.move borrador. Su XmlRpcOdooRepository se reutiliza en op. 1, 2, 5 y 6: búsqueda por ref_num → vat y lectura de tarifas para op. 6")
        Component(catalogs, "Catálogos", "package, provider, special, city, cup, activity", "Repos Sa* de catálogos")
    }

    Container_Boundary(shared, "src/shared") {
        Component(normalizers, "Normalizadores", "text_normalizer, document_normalizer", "normalize_nit (9 díg.), normalize_document (NIT vs cédula, DV DIAN), nombres")
        Component(fuzz, "Fuzzy", "RapidFuzzBiller, CompanyNameMatcher", "token_sort_ratio → partial_ratio")
        Component(excel_io, "Excel", "ExcelLoader, ExcelExporter, MegaDataFrames", "calamine Utf8; export multihoja; origen _HOJA/_FILA en op. 4")
        Component(console, "Consola", "file_input, sheet_input, file_output, RichProgress, USER_CONSOLE", "Prompts validados, progreso y mensajes al usuario en la misma consola")
        Component(logging, "Logging", "LoggerAdapter, TechOnlyLogger, RichHandler", "tech → logs.log · user_msg → consola (TechOnlyLogger lo descarta en op. 6)")
        Component(reporting, "Hallazgos", "FindingsWriter, XlsxFindingsWriter, PhaseFindingsReporter", "Un libro por tipo de hallazgo en logs/<opcion>/<fecha>/")
        Component(config, "Config / BD", "config.py, database.py, models.py", "DIRECTORY, TIAN_NIT, sesión SQLAlchemy")
    }

    Rel(scrapping, odooInjection, "XmlRpcOdooRepository")
    Rel(billers, scrapping, "RUESNitService")
    Rel(company, scrapping, "RUESNitService")
    Rel(assign, scrapping, "RUESNitService")
    Rel(assign, odooInjection, "XmlRpcOdooRepository")
    Rel(assign, company, "Imedical/Tian repos")
    Rel(assign, catalogs, "Catálogos + rates")
    Rel(rates, catalogs, "Upsert catálogos")
    Rel(dataProcessing, catalogs, "Lee cups")
    Rel(preInvoice, catalogs, "Nombres de CUP")
    Rel(assign, normalizers, "NIT, nombres, fechas")
    Rel(company, normalizers, "normalize_document")
    Rel(assign, fuzz, "Ciudades, nombres")
    Rel(preInvoice, excel_io, "openpyxl")
    Rel(billers, reporting, "FindingsWriter")
    Rel(rates, reporting, "FindingsWriter")
    Rel(company, reporting, "FindingsWriter")
    Rel(assign, reporting, "PhaseFindingsReporter")
    Rel(rates, excel_io, "MegaDataFrames")
```

---

## Nivel 4: Diagrama de Código (Módulo Assign)

El módulo más complejo: la asignación de tarifas (opción 6).

```mermaid
classDiagram
    class AssignRatesFromExcel {
        -biller_repo
        -company_repo
        -biller_company_repo
        -package_repo
        -provider_repo
        -special_repo
        -city_repo
        -activities_repo
        -rates_repo: SaRatesRepository
        -cup_repo
        -fuzz: RapidFuzzBiller
        -progress: RichProgress
        -logger: TechOnlyLogger
        -odoo_repo: OdooConnectionRepository
        -not_found_log_generator
        -imedical_repo: ImedicalRepository
        -tian_repo: TianRepository
        -tian_log_generator: TianCompaniesLogGenerator
        -findings_reporter: PhaseFindingsReporter
        -_odoo_by_nit: dict
        -_odoo_index: OdooRateIndex
        +execute(excel, df_facture) AssignRatesResult
        -_load_odoo_rates(df)
        -_resolve_odoo_cells(rows, headers) dict
        -_capture_raw_nit(df)
        -_apply_imedical(df)
        -_match_companies(df)
        -_normalize_columns(df)
        -_apply_tian(df)
        -_normalize_city(df)
        -_assign_facturador(df)
        -_assign_paquete(df)
        -_assign_rates(df) tuple~df, cell_colors~
        -_validate_empresa(df)
        -_enrich_with_invoices(df, df_facture)
        -_write_legend(workbook)
        -_publish_findings() AssignRatesResult
    }

    class OdooConnectionRepository {
        <<abstract>>
        +connect()
        +find_client(nit, name) tuple
        +find_client_by_name(name) tuple
        +find_clients_by_name(name, limit) list~dict~
        +find_clients_batch(nits) dict
        +get_nit(client_id) str
        +find_partner_rates_batch(nits) list~dict~
        +find_rate_lines(rate_ids, cup_codes) list~dict~
    }

    class OdooRateIndex {
        +price(rate_id, city, cup, activity) int
    }

    class AssignRatesResult {
        <<dataclass>>
        +counts: dict
        +findings_dir: Path
        +odoo_available: bool
    }

    class PhaseFindingsReporter {
        <<abstract>>
        +write(findings, companies) Path
    }

    class FindingsWriter {
        <<abstract>>
        +write(books, columns) Path
    }

    class ImedicalRepository {
        <<abstract>>
        +all() list~dict~
        +save_batch(corrections)
    }

    class TianRepository {
        <<abstract>>
        +all() list~dict~
    }

    class ImedicalCorrection {
        <<frozen dataclass>>
        +nit_error
        +nit_success
        +name
        +name_error
    }

    class TianAssignment {
        <<frozen dataclass>>
        +nit_original
        +name_original
        +nit_tian
        +name_final
        +rows
    }

    class RUESNitService {
        +search(nits, rues_cache) list~NitResult~
        +local_updates list~dict~
        +odoo_available bool
        +writer(data, file_path)
    }

    AssignRatesFromExcel --> OdooConnectionRepository
    AssignRatesFromExcel --> ImedicalRepository
    AssignRatesFromExcel --> TianRepository
    AssignRatesFromExcel --> RUESNitService
    AssignRatesFromExcel ..> ImedicalCorrection : crea
    AssignRatesFromExcel ..> TianAssignment : crea
    OdooConnectionRepository <|.. XmlRpcOdooRepository
    ImedicalRepository <|.. SaImedicalRepository
    TianRepository <|.. SaTianRepository
    AssignRatesFromExcel --> PhaseFindingsReporter
    AssignRatesFromExcel ..> OdooRateIndex : crea
    AssignRatesFromExcel ..> AssignRatesResult : devuelve
    PhaseFindingsReporter <|.. XlsxPhaseFindingsReporter
    XlsxPhaseFindingsReporter --> XlsxFindingsWriter
    FindingsWriter <|.. XlsxFindingsWriter
```

---

## Nivel 4: Diagrama de Código (Módulo Scrapping)

```mermaid
classDiagram
    class SearchNitsWithOdooFallbackUseCase {
        -search_nits_use_case: SearchNitsUseCase
        -odoo_repo: OdooConnectionRepository
        -nit_cache_repo: NitCacheRepository
        -name_matcher: CompanyNameMatcher
        -local_name_lookup: bool
        -rues_name_limit: int
        +odoo_available: bool
        +local_updates: list~dict~
        +execute(nits, show_progress, book_names, rues_cache) list~NitResult~
        -_names_differ(book_name, found_name) bool
        -_resolve(...)
    }

    class NitScraperRepository {
        <<abstract>>
        +search_nits(nits, show_progress) list~NitResult~
        +search_by_name(name) NitResult
        +search_names(names) dict
    }

    class NitCacheRepository {
        <<abstract>>
        +get_many(nits) dict
        +get_by_names(names) dict
        +save_many(results) list~str~
    }

    class NitResult {
        +nit: int
        +is_company: bool
        +name: str
        +checked_bases: str
        +source: str
        +nit_original: str
        +name_original: str
        +conflict: str
    }

    SearchNitsWithOdooFallbackUseCase --> SearchNitsUseCase
    SearchNitsWithOdooFallbackUseCase --> NitCacheRepository
    SearchNitsWithOdooFallbackUseCase --> OdooConnectionRepository
    SearchNitsUseCase --> NitScraperRepository
    NitScraperRepository <|.. RuesPlaywrightScraper
    NitCacheRepository <|.. SaCompanyNitCacheRepository
    SearchNitsWithOdooFallbackUseCase ..> NitResult : devuelve
```

---

## Nivel 4: Diagrama de Código (Módulo OdooInjection)

```mermaid
classDiagram
    class InjectInvoicesToOdoo {
        -reader_repo: PreInvoiceReaderRepository
        -odoo_repo: OdooConnectionRepository
        -city_resolver: CityAccountResolver
        -log_generator: ExcelLogGenerator
        -config: dict
        +execute(input_dir, output_dir)
    }

    class PreInvoiceReaderRepository {
        <<abstract>>
        +read_files(directory) tuple
    }

    class OdooConnectionRepository {
        <<abstract>>
        +connect()
        +find_client(nit, name) tuple
        +find_client_by_name(name) tuple
        +find_product(code) dict
        +find_tax(name) int
        +find_uom(name) int
        +find_analytic_account(code) int
        +find_date_range(date) int
        +create_client(nit, name) int
        +create_invoice(vals) int
    }

    class ExcelLogGenerator {
        +generate(resultados, output_dir)
        +read_successful_nits(log_path) set~str~
    }

    InjectInvoicesToOdoo --> PreInvoiceReaderRepository
    InjectInvoicesToOdoo --> OdooConnectionRepository
    InjectInvoicesToOdoo --> CityAccountResolver
    InjectInvoicesToOdoo --> ExcelLogGenerator
    PreInvoiceReaderRepository <|.. ExcelPreInvoiceReader
    OdooConnectionRepository <|.. XmlRpcOdooRepository
```

> `create_client` existe en el puerto, pero el caso de uso nunca lo invoca (ADR-010, "verificar, nunca crear"). Solo llena `vat`, mientras Odoo guarda el NIT en `ref_num`: la spec 012 encontró 54 clientes duplicados creados así. `find_client` delega en `find_clients_batch([nit])`. La opción 8 está deshabilitada en `main.py`.

---

## Flujo: Cascada de validación de empresas (opción 1)

**Odoo es la fuente de verdad** (spec 016): se consulta primero y siempre, también para las empresas que ya están en la BD local. La BD local es el respaldo y se corrige con lo que dice Odoo. `data.json` solo aporta resultados de RUES. Cada paso recibe solo lo que el anterior dejó pendiente. Las opciones 2 y 5 usan la misma cascada (`RUESNitService`); la opción 6 valida sus empresas en el mismo orden con su propia lógica.

```mermaid
flowchart TD
    START[NIT + nombre del libro 'nits'] --> CON{Odoo disponible?}
    CON -->|No| NA["Aviso en consola: Odoo no disponible<br/>sigue con BD local y RUES, sin sincronizar"]
    CON -->|Sí| A{Odoo por NIT<br/>ref_num in → ref_num =like → vat in → vat =like}
    NA --> C
    A -->|Sí| OK[✓ Resuelta]
    A -->|No| B{Odoo por nombre<br/>ilike + fuzzy ≥ 90}
    B -->|Sí| OK
    B -->|No| C{BD local por NIT<br/>respaldo}
    C -->|Sí| OK
    C -->|No| D{BD local por nombre exacto}
    D -->|Sí| OK
    D -->|No| E{RUES por NIT<br/>antes: caché RUES de data.json}
    E -->|Sí| OK
    E -->|No| F{RUES por nombre<br/>≤ RUES_NAME_LOOKUP_LIMIT + fuzzy ≥ 90}
    F -->|Sí| OK
    F -->|No| G["⚠️ is_company=False → empresas_no_encontradas.xlsx<br/>la opción 1 retira los NIT ya resueltos"]
    OK --> SYNC["BD local ← Odoo: agrega o corrige la razón social<br/>conflicto de nombre → no actualiza<br/>→ bd_local_actualizada.xlsx"]
    SYNC --> H[Positivos nuevos de RUES → companies · data.json]
```

## Flujo: Pipeline de Asignar Tarifas (opción 6)

```mermaid
flowchart TD
    IN[Libro de atenciones] --> RAW[_capture_raw_nit<br/>NIT crudo sin truncar]
    RAW --> IM{NIT crudo en imedical?}
    IM -->|Sí| IMC[Reemplaza por nit_success<br/>y bloquea cambios por nombre]
    IM -->|No| N9
    IMC --> N9[normalize_nit → 9 dígitos]
    N9 --> MC[_match_companies<br/>Odoo NIT → Odoo nombre → BD NIT → BD nombre → RUES NIT → RUES nombre]
    MC --> AUTO{Base=IMEDICAL y Odoo<br/>da otro NIT con nombre ≥ 90?}
    AUTO -->|Sí| SAVE[Auto-registro en imedical]
    AUTO -->|No| UNI
    SAVE --> UNI[Unificar nombre por NIT<br/>Odoo > BD > primero visto]
    UNI --> NORM[_normalize_columns<br/>fechas, sufijos, INTRA/EXTRA]
    NORM --> TIAN{NIT en tabla tian<br/>y TIAN_NIT válido?}
    TIAN -->|Sí| TR[Factura a TIAN_NIT · nombre '...TIAN' · empresas_tian.xlsx]
    TIAN -->|No| CITY
    TR --> CITY[_normalize_city fuzzy ≥ 90]
    CITY --> OD["_load_odoo_rates<br/>find_partner_rates_batch + find_rate_lines → OdooRateIndex<br/>Odoo no disponible → índice vacío"]
    OD --> FB["Facturador desde BD, default GENERAL<br/>PAQUETE = tarifa especial Odoo › base › paquete local, default PAQUETE C 2025"]
    FB --> RATES["Tarifa Odoo especial → base<br/>luego cascada local de 6 fases"]
    RATES --> INV{¿día fuera de<br/>DAY_INITIAL–DAY_FINAL?}
    INV -->|Sí| FAC[Cruce con libro de facturas → FACTURAS]
    INV -->|No| OUT
    FAC --> OUT["CONSOLIDADO.xlsx + hoja Leyenda<br/>+ logs/asignar_tarifas/fecha/ + tabla resumen Rich"]
```

## Flujo: Cascada de tarifas (`_assign_rates`)

Por cada celda CUP con valor `1`:

```mermaid
flowchart TD
    S[Celda CUP = 1] --> OE{Tarifa especial Odoo<br/>+ ciudad + CUP + intra}
    OE -->|Sí| CO[Tarifa Odoo · sin color]
    OE -->|No| OB{Tarifa base Odoo<br/>+ ciudad + CUP + intra}
    OB -->|Sí| CO
    OB -->|No| P1{Paquete propio<br/>+ ciudad + CUP + actividad}
    P1 -->|Sí| C1[Fase 1 · #E2EFDA]
    P1 -->|No| P2{PAQUETE C 2025<br/>+ ciudad + CUP}
    P2 -->|Sí| C2[Fase 2 · #FFF2CC]
    P2 -->|No| P3{Cualquier rateable<br/>+ ciudad + CUP}
    P3 -->|Sí| C3[Fase 3 · #F4B183]
    P3 -->|No| H{¿CUP con sufijo -N<br/>y base existe?}
    H -->|No| P6
    H -->|Sí| P4{PAQUETE C 2025<br/>+ ciudad + CUP base}
    P4 -->|Sí| C4[Fase 4 · #BDD7EE]
    P4 -->|No| P5{Cualquier rateable<br/>+ ciudad + CUP base}
    P5 -->|Sí| C5[Fase 5 · #9DC3E6]
    P5 -->|No| P6{Cualquier rateable<br/>+ cualquier ciudad + CUP}
    P6 -->|Sí| C6[Fase 6 · #D5A6E6]
    P6 -->|No| X["Sin resolver · valor 1 → sin_resolver.xlsx / opción 9"]
```

> Las fases 3, 5 y 6 toman la primera fila que devuelve la BD (consulta sin `ORDER BY`). Odoo: solo precios > 0, sin validar la vigencia de la tarifa; la ciudad se compara por nombre normalizado exacto. Cada fase local (1–6) y el sin resolver van a su libro en `logs/asignar_tarifas/<fecha>/`.

## Flujo: Inyección a Odoo (opción 8, deshabilitada)

```mermaid
flowchart TD
    A[Leer pre-facturas/General sin factura] --> B[Agrupar por NIT]
    B --> C[Excluir NIT con estado OK en log_inyeccion.xlsx]
    C --> D{Cliente: ref_num = NIT}
    D -->|No| E{ref_num =like 'NIT%'}
    E -->|No| E2{vat = NIT}
    E2 -->|No| E3{vat =like 'NIT%'}
    E3 -->|No| F{name ilike sin sufijo societario}
    F -->|No| V["VERIFICAR (nunca se crea el cliente)"]
    D -->|Sí| L
    E -->|Sí| L
    E2 -->|Sí| L
    E3 -->|Sí| L
    F -->|Sí| L[Armar líneas: producto por CUP,<br/>cuenta analítica por ciudad, impuestos]
    L --> LL{¿Hay líneas válidas?}
    LL -->|No| ER[ERROR]
    LL -->|Sí| M[account.move out_invoice borrador]
    M --> OK[OK + link]
    V --> LOG[Fusionar y escribir log_inyeccion.xlsx]
    ER --> LOG
    OK --> LOG
```

---

## Diagrama de Flujo de Datos (ciclo mensual)

```mermaid
flowchart LR
    subgraph IN[Entradas Excel]
        X1[Libro nits]
        X2[Libro gestores]
        X3[Libro de tarifas]
        X5[Libro empresas-paquetes]
        X6[Libro atenciones]
        X6b[Libro facturas]
    end

    subgraph BD[PostgreSQL]
        T1[(companies)]
        T2[(billers / companies_billers)]
        T3[(packages / providers / specials / cities)]
        T4[(rates)]
        T5[(companies_packages)]
        T6[(cups / type_activities)]
        T7[(imedical / tian)]
    end

    ODOO[(Odoo: res.partner / account.base.rate)]

    X1 --> O1[1 Web Scrapping] --> T1
    ODOO --> O1
    ODOO --> O5
    ODOO -->|tarifas especial/base| O6
    O1 --> J[data.json]
    X2 --> O2[2 Facturadores] --> T2
    J --> O2
    X3 --> O3[3 Tratamiento] --> N[facturacion_normalizada.xlsx]
    T6 --> O3
    N --> O4[4 Cargar Tarifas] --> T3 & T4
    X5 --> O5[5 Registrar Empresas] --> T5
    J --> O5
    O5 --> T1
    X6 --> O6[6 Asignar Tarifas]
    X6b -.->|fuera de rango de días| O6
    T1 & T2 & T3 & T4 & T5 & T7 --> O6
    O6 --> CONS[CONSOLIDADO.xlsx]
    O6 --> T7
    CONS --> O9[9 Faltantes] --> FALTANTES[faltantes.xlsx]
    CONS --> O7[7 Pre Facturas] --> PF[pre-facturas/]
    PF -.-> O8[8 Inyección Odoo<br/>deshabilitada]
    T1 --> O10[10 Duplicados] --> DUP[empresas_duplicadas.xlsx]
    O2 --> F2["logs/facturadores/"]
    O4 --> F4["logs/cargar_tarifas/"]
    O5 --> F5["logs/registrar_empresas/"]
    O6 --> F6["logs/asignar_tarifas/"]
    FALTANTES -.->|completar tarifas| X3
```

---

## Diagrama de Despliegue

```mermaid
C4Deployment
    title Diagrama de Despliegue

    Deployment_Node(local, "Equipo del facturador", "Linux / WSL2 / Windows") {
        Deployment_Node(python, "Python 3.12 + venv") {
            Container(app, "Facturación CLI", "main.py", "Proceso interactivo único")
        }
        Deployment_Node(browser, "Firefox headless") {
            Container(pw, "Playwright", "", "Scraping RUES (concurrencia 1-5)")
        }
        Deployment_Node(fs, "Carpeta del proyecto / DIRECTORY") {
            Container(files, "Excel y JSON", ".xlsx / .json", "CONSOLIDADO.xlsx, pre-facturas/, data.json")
            Container(logs, "Logs", ".xlsx / .log", "logs/*.xlsx, user_audit.xlsx, logs.log")
        }
    }

    Deployment_Node(cloud_db, "Supabase") {
        ContainerDb(database, "PostgreSQL", "SUPABASE_DB_*", "BD de facturación")
    }

    Deployment_Node(cloud_odoo, "Avancys Cloud") {
        Container(odoo, "Odoo 14 (soandesv14)", "XML-RPC", "Clientes y facturas")
    }

    Deployment_Node(internet, "Internet") {
        System_Ext(rues, "www.rues.org.co", "Consulta empresarial")
    }

    Rel(app, database, "psycopg2", "TCP 5432 / sslmode=require")
    Rel(app, odoo, "XML-RPC", "HTTPS 443")
    Rel(app, pw, "Playwright API")
    Rel(pw, rues, "HTTPS", "443")
    Rel(app, files, "Lee / escribe")
    Rel(app, logs, "Escribe")
```

> Alembic usa `DATABASE_URL` si está definida (si no, `SUPABASE_DB_*` con puerto por defecto 6543). La aplicación usa siempre `SUPABASE_DB_*` (puerto por defecto 5432).

---

## Cómo renderizar los diagramas

Los diagramas se renderizan automáticamente en:

- GitHub / GitLab
- VS Code con la extensión "Markdown Preview Mermaid Support"
- [mermaid.live](https://mermaid.live)

Para generar imágenes estáticas:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/c4-diagrams.md -o docs/diagrams/c4.png
```
