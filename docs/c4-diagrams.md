# Diagramas C4 - Sistema de Facturación SOANDES

Diagramas arquitectónicos siguiendo el modelo C4 (Context, Container, Component, Code).
Notación: [Mermaid](https://mermaid.js.org/) para renderizado en GitHub/GitLab.

---

## Nivel 1: Diagrama de Contexto

Muestra el sistema y sus interacciones con actores y sistemas externos.

```mermaid
C4Context
    title Sistema de Facturación SOANDES - Diagrama de Contexto

    Person(usuario, "Operador de Facturación", "Personal administrativo que ejecuta el proceso de facturación mensual")

    System(facturacion, "Sistema de Facturación SOANDES", "Aplicación CLI que automatiza la importación de datos, asignación de tarifas, generación de pre-facturas e inyección a Odoo")

    System_Ext(rues, "RUES", "Registro Único Empresarial y Social de Colombia - Validación de NITs y nombres de empresas")
    System_Ext(supabase, "PostgreSQL", "Base de datos relacional para catálogos y tarifas")
    System_Ext(odoo, "Odoo 14 / Avancys", "ERP destino para inyección de facturas via XML-RPC")
    System_Ext(excel, "Archivos Excel", "Fuentes de datos: tarifas, empresas, facturadores, consolidados")

    Rel(usuario, facturacion, "Ejecuta procesos via menú CLI")
    Rel(facturacion, rues, "Consulta NITs y nombres via web scraping", "HTTPS/Playwright")
    Rel(facturacion, supabase, "Lee/escribe catálogos y tarifas", "PostgreSQL/TCP")
    Rel(facturacion, odoo, "Inyecta facturas y busca clientes", "XML-RPC/HTTPS")
    Rel(facturacion, excel, "Lee datos de entrada, genera consolidados y pre-facturas", "openpyxl/xlsxwriter")
    Rel(usuario, excel, "Provee archivos de entrada")
```

---

## Nivel 2: Diagrama de Contenedores

Muestra los componentes técnicos principales del sistema.

```mermaid
C4Container
    title Sistema de Facturación SOANDES - Diagrama de Contenedores

    Person(usuario, "Operador de Facturación")

    System_Boundary(sistema, "Sistema de Facturación") {
        Container(cli, "Aplicación CLI", "Python 3.12 / Rich", "Interfaz de menú interactivo para ejecutar procesos de facturación")
        Container(core, "Core de Negocio", "Python / Polars", "Casos de uso: importación, normalización, asignación, inyección")
        Container(scraper, "Web Scraper", "Playwright / BeautifulSoup", "Consultas al RUES por NIT y por nombre de empresa")
        Container(odoo_client, "Odoo Client", "XML-RPC", "Inyección de facturas y búsqueda de clientes en Avancys")
        Container(persistence, "Capa de Persistencia", "SQLAlchemy 2.0 / Alembic", "Repositorios de acceso a datos con patrón Repository")
        Container(etl, "Motor ETL", "Polars / fastexcel", "Procesamiento y transformación de datos desde/hacia Excel")
        Container(logging_sys, "Sistema de Logging", "ExcelAuditHandler", "Auditoría en Excel + logs técnicos rotativos")
    }

    System_Ext(rues, "RUES", "Portal web de consulta empresarial")
    System_Ext(odoo, "Odoo 14 / Avancys", "ERP con datos de clientes y facturas")
    ContainerDb(db, "PostgreSQL", "Base de datos relacional", "Catálogos: empresas, facturadores, tarifas, CUPS, ciudades, paquetes")
    System_Ext(fs, "Sistema de Archivos", "Archivos Excel de entrada/salida + logs")

    Rel(usuario, cli, "Interactúa via terminal")
    Rel(cli, core, "Invoca casos de uso")
    Rel(core, persistence, "Consulta/persiste datos")
    Rel(core, etl, "Procesa DataFrames")
    Rel(core, scraper, "Valida NITs y busca empresas")
    Rel(core, odoo_client, "Inyecta facturas, busca clientes")
    Rel(core, logging_sys, "Registra auditoría y errores")
    Rel(scraper, rues, "HTTP/Playwright")
    Rel(odoo_client, odoo, "XML-RPC/HTTPS")
    Rel(persistence, db, "SQL/psycopg2")
    Rel(etl, fs, "Lee/escribe .xlsx")
    Rel(logging_sys, fs, "Escribe user_audit.xlsx + logs.log")
```

---

## Nivel 3: Diagrama de Componentes

Detalle de los módulos internos del Core de Negocio.

```mermaid
C4Component
    title Core de Negocio - Diagrama de Componentes

    Container_Boundary(core, "Core de Negocio") {

        Component(assign, "Assign Module", "AssignRatesFromExcel", "Cascada de resolución de empresas (6 pasos). Normaliza NITs, fechas, sufijos corporativos. Fuzzy matching.")

        Component(preInvoice, "PreInvoice Module", "SplitByNit", "Genera archivos Excel individuales por NIT. Clasifica carpeta SET vs GENERAL.")

        Component(rates, "Rates Module", "ImportRatesFromExcel", "Importa tarifas con dedup batch. Fuzzy city resolution. Rename de tarifas especiales por año.")

        Component(billers, "Billers Module", "ImportBillersFromExcel", "Importa facturadores. Dedup por company_id con log de omitidos.")

        Component(company, "Company Module", "ImportCompaniesFromExcel", "Registra empresas. Scraping + cache JSON. Vinculación con paquetes.")

        Component(dataProcessing, "DataProcessing Module", "NormalizeInformationFromExcel", "Normaliza datos de paquetes, proveedores y tarifas especiales.")

        Component(scrapping, "Scrapping Module", "RUESNitService", "Busca por NIT y por nombre con retry (3 intentos, 5s delay).")

        Component(odooInjection, "OdooInjection Module", "InjectInvoicesToOdoo", "Anti-duplicados. Búsqueda NIT (=like) → nombre → VERIFICAR. Log Excel.")
    }

    Container_Boundary(shared, "Shared") {
        Component(fuzz, "RapidFuzzBiller", "Fuzzy Matching", "Matching difuso con token_sort_ratio + partial_ratio")
        Component(excel_io, "Excel I/O", "ExcelLoader + ExcelExporter", "Carga y exportación de archivos Excel")
        Component(logging, "Logging System", "LoggerAdapter + ExcelAuditHandler", "Logging dual: auditoría Excel + técnico rotativo")
        Component(progress, "Progress", "RichProgress", "Barras de progreso para operaciones largas")
        Component(db_layer, "Database", "SQLAlchemy SessionLocal", "Conexión y sesiones de BD")
    }

    Rel(assign, fuzz, "Resuelve nombres")
    Rel(assign, scrapping, "Cascada pasos 3-4")
    Rel(assign, odooInjection, "Cascada pasos 5-6")
    Rel(assign, db_layer, "Consulta catálogos")
    Rel(assign, excel_io, "Exporta consolidado")
    Rel(preInvoice, excel_io, "Lee consolidado, escribe pre-facturas")
    Rel(rates, db_layer, "Persiste tarifas")
    Rel(rates, fuzz, "Fuzzy city resolution")
    Rel(billers, db_layer, "Persiste facturadores")
    Rel(company, db_layer, "Persiste empresas")
    Rel(company, scrapping, "Valida NITs nuevos")
    Rel(dataProcessing, excel_io, "Lee/escribe Excel normalizado")
    Rel(odooInjection, excel_io, "Lee/escribe log de inyección")
```

---

## Nivel 4: Diagrama de Código (Módulo Assign)

Detalle del módulo más complejo: asignación de tarifas.

```mermaid
classDiagram
    class AssignRatesFromExcel {
        -biller_repo: BillerRepository
        -company_repo: CompanyRepository
        -biller_company_repo: BillerCompanyRepository
        -package_repo: PackageRepository
        -provider_repo: ProviderRepository
        -special_repo: SpecialRepository
        -city_repo: CityRepository
        -activities_repo: ActivityRepository
        -rates_repo: RatesRepository
        -cup_repo: CupRepository
        -nit_service: RUESNitService
        -odoo_repo: OdooConnectionRepository
        -fuzz: RapidFuzzBiller
        -progress: RichProgress
        -logger: LoggerAdapter
        +execute(df, df_facture)
        -_match_companies(df)
        -_normalize_nit(nit) str
        -_normalize_columns(df) DataFrame
        -_normalize_fecha(df) DataFrame
    }

    class OdooConnectionRepository {
        <<abstract>>
        +find_client(nit) dict|None
        +find_client_by_name(name) dict|None
        +get_nit(partner_id) str|None
        +create_invoice(data) int|None
    }

    class XmlRpcOdooRepository {
        -url: str
        -db: str
        -uid: int
        -password: str
        +find_client(nit) dict|None
        +find_client_by_name(name) dict|None
        +get_nit(partner_id) str|None
    }

    class RUESNitService {
        -_scraper: NitScraperRepository
        -logger: LoggerAdapter
        +search(nits) list~NitResult~
        +search_by_name(name) NitResult|None
        +writer(data, file_path)
    }

    class RapidFuzzBiller {
        -logger: LoggerAdapter
        +fuzz_property(name, catalog, threshold) str|None
    }

    AssignRatesFromExcel --> OdooConnectionRepository
    AssignRatesFromExcel --> RUESNitService
    AssignRatesFromExcel --> RapidFuzzBiller
    OdooConnectionRepository <|.. XmlRpcOdooRepository
```

---

## Nivel 4: Diagrama de Código (Módulo OdooInjection)

```mermaid
classDiagram
    class InjectInvoicesToOdoo {
        -odoo_repo: OdooConnectionRepository
        -log_generator: ExcelLogGenerator
        -logger: LoggerAdapter
        +execute(df, log_path)
        -_filter_already_processed(empresas, log_path)
    }

    class ExcelLogGenerator {
        +generate(results, path)
        +read_successful_nits(path)$ set~str~
    }

    class OdooConnectionRepository {
        <<abstract>>
        +find_client(nit) dict|None
        +find_client_by_name(name) dict|None
        +get_nit(partner_id) str|None
        +create_invoice(data) int|None
    }

    class XmlRpcOdooRepository {
        -url: str
        -db: str
        -uid: int
        -models: ServerProxy
        -_cache: dict
        +find_client(nit) dict|None
        +find_client_by_name(name) dict|None
        +get_nit(partner_id) str|None
        +create_invoice(data) int|None
    }

    InjectInvoicesToOdoo --> OdooConnectionRepository
    InjectInvoicesToOdoo --> ExcelLogGenerator
    OdooConnectionRepository <|.. XmlRpcOdooRepository
```

---

## Nivel 4: Diagrama de Código (Módulo Scrapping)

```mermaid
classDiagram
    class NitScraperRepository {
        <<abstract>>
        +search_nits(nits, show_progress) list~NitResult~
        +search_by_name(name) NitResult|None
    }

    class RuesPlaywrightScraper {
        -logger: LoggerAdapter
        +search_nits(nits, show_progress) list~NitResult~
        +search_by_name(name) NitResult|None
    }

    class RUESNitService {
        -_scraper: NitScraperRepository
        -logger: LoggerAdapter
        +search(nits) list~NitResult~
        +search_by_name(name) NitResult|None
        +writer(data, file_path)
    }

    class NitResult {
        +nit: int
        +is_company: bool
        +name: str|None
    }

    RUESNitService --> NitScraperRepository
    NitScraperRepository <|.. RuesPlaywrightScraper
    RUESNitService ..> NitResult : returns
```

---

## Diagrama de Flujo: Cascada de Resolución de Empresas

```mermaid
flowchart TD
    START[Fila del Excel con NIT + Nombre] --> A{BD local por NIT?}
    A -->|Sí| DONE[✓ Empresa resuelta]
    A -->|No| B{BD local por Nombre?}
    B -->|Sí| DONE
    B -->|No| C{RUES por NIT?}
    C -->|Sí| DONE
    C -->|No| D{RUES por Nombre?}
    D -->|Sí| DONE
    D -->|No| E{Odoo por NIT =like?}
    E -->|Sí| DONE
    E -->|No| F{Odoo por Nombre ilike?}
    F -->|Sí| DONE
    F -->|No| G["⚠️ [NOVEDAD] - Sin resultado"]
```

---

## Diagrama de Flujo: Inyección a Odoo

```mermaid
flowchart TD
    A[Leer log previo de inyección] --> B[Filtrar NITs ya procesados OK]
    B --> C[Para cada empresa del batch]
    C --> D{Buscar cliente por NIT =like}
    D -->|Encontrado| G[Crear factura en Odoo]
    D -->|No encontrado| E{Buscar por nombre ilike}
    E -->|Encontrado| G
    E -->|No encontrado| F["Marcar VERIFICAR"]
    G --> H[Registrar resultado en log Excel]
    F --> H
    H --> I{¿Más empresas?}
    I -->|Sí| C
    I -->|No| J[Escribir log_inyeccion.xlsx]
```

---

## Diagrama de Flujo de Datos

```mermaid
flowchart TD
    A[Archivos Excel de Entrada] --> B{Menú CLI}

    B -->|Opción 1| C[Web Scrapping RUES]
    B -->|Opción 2| D[Importar Facturadores]
    B -->|Opción 3| E[Normalizar Información]
    B -->|Opción 4| F[Cargar Tarifas]
    B -->|Opción 5| G[Registrar Empresas]
    B -->|Opción 6| H[Asignar Tarifas]
    B -->|Opción 7| K[Inyectar a Odoo]

    C --> C1[Validar NITs en RUES]
    C1 --> C2[JSON con resultados]

    D --> D1[Excel → Polars DataFrame]
    D1 --> D2[Dedup por company_id]
    D2 --> D3[Persistir en BD]

    E --> E1[Leer hojas: Paquetes, Proveedores, Especiales]
    E1 --> E2[Normalizar nombres y datos]
    E2 --> E3[Exportar Excel normalizado]

    F --> F1[Leer tarifas desde Excel]
    F1 --> F2[Fuzzy city resolution]
    F2 --> F3[Rename tarifas especiales]
    F3 --> F4[Dedup por clave compuesta]
    F4 --> F5[Persistir rates en BD]

    G --> G1[Leer empresas desde Excel]
    G1 --> G2[Validar NITs RUES o cache JSON]
    G2 --> G3[Asociar con paquetes]
    G3 --> G4[Persistir en BD]

    H --> H1[Leer consolidado Excel]
    H1 --> H2[Cascada resolución empresas]
    H2 --> H3[Normalizar NITs, fechas, sufijos]
    H3 --> H4[Cruzar con catálogos BD]
    H4 --> H5[Calcular tarifas por CUPS]
    H5 --> H6[Generar CONSOLIDADO.xlsx]
    H6 --> H7{¿Día < 5 o > 29?}
    H7 -->|Sí| I[Generar Pre-Facturas por NIT]
    H7 -->|No| J[Fin]

    K --> K1[Leer pre-facturas]
    K1 --> K2[Filtrar anti-duplicados]
    K2 --> K3[Buscar clientes en Odoo]
    K3 --> K4[Inyectar facturas XML-RPC]
    K4 --> K5[Generar log_inyeccion.xlsx]

    I --> J

    subgraph BD[PostgreSQL / Supabase]
        DB1[(companies)]
        DB2[(billers)]
        DB3[(rates)]
        DB4[(cups)]
        DB5[(cities)]
        DB6[(packages)]
        DB7[(providers)]
        DB8[(specials)]
    end

    D3 --> BD
    F5 --> BD
    G4 --> BD
    H4 --> BD
```

---

## Diagrama de Despliegue

```mermaid
C4Deployment
    title Diagrama de Despliegue

    Deployment_Node(local, "Máquina Local del Operador", "Ubuntu/Windows") {
        Deployment_Node(python, "Python 3.12 Runtime") {
            Container(app, "Facturación CLI", "main.py", "Aplicación de consola interactiva")
        }
        Deployment_Node(browser, "Firefox Headless") {
            Container(pw, "Playwright", "", "Navegador para web scraping RUES")
        }
        Deployment_Node(fs, "Sistema de Archivos") {
            Container(excel_in, "Excel Input", ".xlsx", "Archivos de datos de entrada")
            Container(excel_out, "Excel Output", ".xlsx", "Consolidados y pre-facturas generadas")
            Container(logs, "Logs", ".xlsx/.log", "user_audit.xlsx + logs.log")
        }
    }

    Deployment_Node(cloud_sb, "Servidor de Base de Datos") {
        Deployment_Node(pg, "PostgreSQL 15") {
            ContainerDb(database, "postgres", "Base de datos de facturación")
        }
    }

    Deployment_Node(cloud_odoo, "Avancys Cloud") {
        Deployment_Node(odoo_server, "Odoo 14") {
            Container(odoo, "soandesv14", "ERP con datos de clientes y facturas")
        }
    }

    Deployment_Node(internet, "Internet") {
        Deployment_Node(rues_server, "RUES Server") {
            System_Ext(rues, "www.rues.org.co", "Portal de consulta empresarial")
        }
    }

    Rel(app, database, "psycopg2", "TCP/5432")
    Rel(app, odoo, "XML-RPC", "HTTPS/443")
    Rel(pw, rues, "HTTPS", "443")
    Rel(app, pw, "Playwright API")
    Rel(app, excel_in, "Lee")
    Rel(app, excel_out, "Escribe")
    Rel(app, logs, "Escribe")
```

---

## Cómo Renderizar los Diagramas

Los diagramas están escritos en **Mermaid** y se renderizan automáticamente en:
- GitHub (README, issues, PRs)
- GitLab
- VS Code con extensión "Mermaid Preview"
- [mermaid.live](https://mermaid.live) (editor online)

Para generar imágenes estáticas:
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/c4-diagrams.md -o docs/diagrams/ -e png
```
