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

    System(facturacion, "Sistema de Facturación SOANDES", "Aplicación CLI que automatiza la importación de datos, asignación de tarifas y generación de pre-facturas")

    System_Ext(rues, "RUES", "Registro Único Empresarial y Social de Colombia - Validación de NITs")
    System_Ext(supabase, "Supabase (PostgreSQL)", "Base de datos relacional en la nube para catálogos y tarifas")
    System_Ext(excel, "Archivos Excel", "Fuentes de datos: tarifas, empresas, facturadores, consolidados")

    Rel(usuario, facturacion, "Ejecuta procesos via menú CLI")
    Rel(facturacion, rues, "Consulta NITs via web scraping", "HTTPS/Playwright")
    Rel(facturacion, supabase, "Lee/escribe catálogos y tarifas", "PostgreSQL/SSL")
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
        Container(core, "Core de Negocio", "Python / Polars", "Casos de uso: importación, normalización, asignación de tarifas, generación de pre-facturas")
        Container(scraper, "Web Scraper", "Playwright / BeautifulSoup", "Automatización de consultas al RUES para validación de NITs")
        Container(persistence, "Capa de Persistencia", "SQLAlchemy 2.0 / Alembic", "Repositorios de acceso a datos con patrón Repository")
        Container(etl, "Motor ETL", "Polars / fastexcel", "Procesamiento y transformación de datos desde/hacia Excel")
    }

    System_Ext(rues, "RUES", "Portal web de consulta empresarial")
    ContainerDb(db, "PostgreSQL", "Supabase", "Catálogos: empresas, facturadores, tarifas, CUPS, ciudades, paquetes")
    System_Ext(fs, "Sistema de Archivos", "Archivos Excel de entrada/salida")

    Rel(usuario, cli, "Interactúa via terminal")
    Rel(cli, core, "Invoca casos de uso")
    Rel(core, persistence, "Consulta/persiste datos")
    Rel(core, etl, "Procesa DataFrames")
    Rel(core, scraper, "Valida NITs")
    Rel(scraper, rues, "HTTP/Playwright")
    Rel(persistence, db, "SQL/psycopg2")
    Rel(etl, fs, "Lee/escribe .xlsx")
```

---

## Nivel 3: Diagrama de Componentes

Detalle de los módulos internos del Core de Negocio.

```mermaid
C4Component
    title Core de Negocio - Diagrama de Componentes

    Container_Boundary(core, "Core de Negocio") {

        Component(assign, "Assign Module", "AssignRatesFromExcel", "Asigna tarifas a registros cruzando con catálogos de BD. Usa fuzzy matching para resolver nombres.")

        Component(preInvoice, "PreInvoice Module", "SplitByNit", "Genera archivos Excel individuales por NIT desde el consolidado.")

        Component(rates, "Rates Module", "ImportRatesFromExcel", "Importa tarifas desde Excel y las persiste en BD con relaciones polimórficas.")

        Component(billers, "Billers Module", "ImportBillersFromExcel", "Importa facturadores desde Excel y los asocia con empresas.")

        Component(company, "Company Module", "ImportCompaniesFromExcel", "Registra empresas y sus relaciones con paquetes y facturadores.")

        Component(dataProcessing, "DataProcessing Module", "NormalizeInformationFromExcel", "Normaliza datos de paquetes, proveedores y tarifas especiales.")

        Component(scrapping, "Scrapping Module", "SearchNitsUseCase", "Valida NITs consultando el RUES via web scraping.")
    }

    Container_Boundary(shared, "Shared") {
        Component(fuzz, "RapidFuzzBiller", "Fuzzy Matching", "Matching difuso de nombres con threshold configurable")
        Component(excel_io, "Excel I/O", "ExcelLoader + ExcelExporter", "Carga y exportación de archivos Excel")
        Component(logging, "Logging System", "LoggerAdapter", "Logging dual: usuario + técnico")
        Component(progress, "Progress", "RichProgress", "Barras de progreso para operaciones largas")
        Component(db_layer, "Database", "SQLAlchemy SessionLocal", "Conexión y sesiones de BD")
    }

    Rel(assign, fuzz, "Resuelve nombres")
    Rel(assign, db_layer, "Consulta catálogos")
    Rel(assign, excel_io, "Exporta consolidado")
    Rel(preInvoice, excel_io, "Lee consolidado, escribe pre-facturas")
    Rel(rates, db_layer, "Persiste tarifas")
    Rel(billers, db_layer, "Persiste facturadores")
    Rel(company, db_layer, "Persiste empresas")
    Rel(dataProcessing, excel_io, "Lee/escribe Excel normalizado")
    Rel(scrapping, progress, "Muestra progreso")
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
        -fuzz: RapidFuzzBiller
        -progress: RichProgress
        -logger: LoggerAdapter
        +execute(df: DataFrame, df_facture: DataFrame)
    }

    class BillerRepository {
        <<abstract>>
        +find_by_name(name: str)
        +save(biller)
        +save_batch(billers: list)
        +all()
    }

    class CompanyRepository {
        <<abstract>>
        +find_by_nit(nit: str)
        +save(company)
        +save_batch(companies: list)
        +find_by_name(name: str)
        +all()
    }

    class RatesRepository {
        <<abstract>>
        +find_rates(rateable_id, city_id, cup_id, activity_id, rateable_type)
        +save_batch(rates: list)
    }

    class RapidFuzzBiller {
        -logger: LoggerAdapter
        +fuzz_property(property_name: str, catalog: list, threshold: int): str|None
    }

    class RUESNitService {
        -logger: LoggerAdapter
        +search(nits): list~NitResult~
        +writer(data, file_path)
    }

    class SaBillerRepository {
        -session: Session
        -logger: LoggerAdapter
        +find_by_name(name: str)
        +save(biller)
        +save_batch(billers: list)
        +all()
    }

    class SaCompanyRepository {
        -session: Session
        -logger: LoggerAdapter
        +find_by_nit(nit: str)
        +save(company)
        +save_batch(companies: list)
        +find_by_name(name: str)
        +all()
    }

    AssignRatesFromExcel --> BillerRepository
    AssignRatesFromExcel --> CompanyRepository
    AssignRatesFromExcel --> RatesRepository
    AssignRatesFromExcel --> RapidFuzzBiller
    AssignRatesFromExcel --> RUESNitService
    BillerRepository <|.. SaBillerRepository
    CompanyRepository <|.. SaCompanyRepository
```

---

## Nivel 4: Diagrama de Código (Módulo Scrapping)

```mermaid
classDiagram
    class SearchNitsUseCase {
        -scraper: NitScraperRepository
        +execute(nits: list, show_progress: bool): list~NitResult~
    }

    class NitScraperRepository {
        <<abstract>>
        +search_nits(nits: list, show_progress: bool): list~NitResult~
    }

    class RuesPlaywrightScraper {
        -logger: LoggerAdapter
        +search_nits(nits: list, show_progress: bool): list~NitResult~
        -_search_nits_async(nits, show_progress): list~NitResult~
    }

    class NitResult {
        +nit: int
        +is_company: bool
        +name: str | None
    }

    class RUESNitService {
        -logger: LoggerAdapter
        +search(nits): list~NitResult~
        +writer(data, file_path)
    }

    SearchNitsUseCase --> NitScraperRepository
    NitScraperRepository <|.. RuesPlaywrightScraper
    RUESNitService --> SearchNitsUseCase
    SearchNitsUseCase ..> NitResult : returns
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

    C --> C1[Validar NITs en RUES]
    C1 --> C2[JSON con resultados]

    D --> D1[Excel → Polars DataFrame]
    D1 --> D2[Persistir en BD]

    E --> E1[Leer hojas: Paquetes, Proveedores, Especiales]
    E1 --> E2[Normalizar nombres y datos]
    E2 --> E3[Exportar Excel normalizado]

    F --> F1[Leer tarifas desde Excel]
    F1 --> F2[Validar CUPS, ciudades, actividades]
    F2 --> F3[Persistir rates en BD]

    G --> G1[Leer empresas desde Excel]
    G1 --> G2[Asociar con paquetes y facturadores]
    G2 --> G3[Persistir en BD]

    H --> H1[Leer consolidado Excel]
    H1 --> H2[Cruzar con catálogos BD]
    H2 --> H3[Fuzzy matching de nombres]
    H3 --> H4[Calcular tarifas por CUPS]
    H4 --> H5[Generar CONSOLIDADO.xlsx]
    H5 --> H6{¿Día < 5 o > 29?}
    H6 -->|Sí| I[Generar Pre-Facturas]
    H6 -->|No| J[Fin]

    I --> I1[Separar por NIT]
    I1 --> I2[Generar Excel por empresa]
    I2 --> J

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

    D2 --> BD
    F3 --> BD
    G3 --> BD
    H2 --> BD
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
            Container(pw, "Playwright", "", "Navegador para web scraping")
        }
        Deployment_Node(fs, "Sistema de Archivos") {
            Container(excel_in, "Excel Input", ".xlsx", "Archivos de datos de entrada")
            Container(excel_out, "Excel Output", ".xlsx", "Consolidados y pre-facturas generadas")
            Container(logs, "Logs", ".log", "user_audit.log + logs.log")
        }
    }

    Deployment_Node(cloud, "Supabase Cloud", "AWS") {
        Deployment_Node(pg, "PostgreSQL 15") {
            ContainerDb(database, "postgres", "Base de datos de facturación")
        }
    }

    Deployment_Node(internet, "Internet") {
        Deployment_Node(rues_server, "RUES Server") {
            System_Ext(rues, "www.rues.org.co", "Portal de consulta empresarial")
        }
    }

    Rel(app, database, "psycopg2 + SSL", "TCP/6543")
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
