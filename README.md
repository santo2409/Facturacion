# Facturación SOANDES

Sistema CLI para automatizar el proceso de facturación de SOANDES: importación de datos desde Excel, validación de NITs, asignación de tarifas, generación de pre-facturas e inyección de facturas en Odoo/Avancys.

## Requisitos

- Python 3.12+
- PostgreSQL
- Firefox (para web scraping RUES)
- Acceso a Odoo 14 / Avancys (validación de clientes, tarifas oficiales de la opción 3 en solo lectura e inyección de facturas)

## Instalación

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
playwright install firefox
```

## Configuración

Crear archivo `.env` en la raíz del proyecto:

```env
SUPABASE_DB_USER=tu_usuario
SUPABASE_DB_PASSWORD=tu_contraseña
SUPABASE_DB_HOST=tu_host
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
DIRECTORY=.

# Odoo / Avancys
ODOO_URL=https://soandesv14.avancyserp.com
ODOO_DB=soandesv14
ODOO_USERNAME=tu_usuario_odoo
ODOO_API_KEY=tu_api_key_odoo

# Negocio
DAY_INITIAL=5
DAY_FINAL=29
TIAN_NIT=
BOOK_ROUTE=/ruta/a/la/carpeta
BOOK_NAME=libro_nits.xlsx
```

La lista completa de variables, con sus valores por defecto, está en la [Documentación Técnica](docs/TECHNICAL_DOCUMENTATION.md#42-variables-de-entorno-env-plantilla-en-envexample).

## Migraciones

```bash
alembic upgrade head
```

## Uso

```bash
python main.py
```

### Menú Principal

| Opción | Función | Descripción |
|--------|---------|-------------|
| 1 | Web Scrapping | Valida NITs/nombres: Odoo → BD local → RUES; corrige la BD local con lo que dice Odoo |
| 2 | Facturadores | Importa facturadores y los vincula con empresas (validadas contra Odoo) |
| 3 | Asignar Tarifas | Tarifa Odoo (especial → base), luego cascada local de 6 fases; i-medical, TIAN → `CONSOLIDADO.xlsx` + libros por fase |
| 4 | Generar Pre Facturas | Separa el CONSOLIDADO por facturador y NIT |
| 5 | Cargar Pre Facturas | Crea una factura borrador por empresa en Odoo (integración de ETL-Avancys) |
| 6 | Empresas Facturadas a Otro NIT | Carga desde Excel las empresas que se facturan bajo otro NIT (TIAN, VISE, RSG…) |

### Flujo típico de facturación

```
1 → 2 → 3 (asignar tarifas; revisar sin_resolver.xlsx) → 4 (pre-facturas)
```

Las tarifas, los paquetes de cada empresa y el catálogo de CUPs se mantienen fuera de esta aplicación (Odoo y la base de datos).
La opción 3 pide además el libro de números de factura cuando el día del mes está fuera del rango `DAY_INITIAL`–`DAY_FINAL`.

Ver la [Guía de Usuario](docs/USER_GUIDE.md) para el detalle de cada opción.

## Características Principales

- **Odoo, fuente de verdad**: las empresas se validan siempre contra Odoo (opciones 1, 2 y 3), también las que ya están en la BD local; la BD local es el respaldo y se corrige con lo que dice Odoo (libro `bd_local_actualizada`). Solo lectura
- **Cascada de resolución de empresas**: Odoo → BD local → RUES (por NIT y por nombre; en Odoo por `ref_num`, con respaldo en `vat`)
- **Tarifas desde Odoo**: la tarifa especial/base de cada empresa en Odoo es la fuente principal de la opción 3; la BD local es el respaldo. Solo lectura
- **Normalización inteligente**: NITs (9 dígitos), fechas (smart swap dd/mm), sufijos corporativos (S.A.S → SAS)
- **Fuzzy matching**: resolución de nombres con RapidFuzz (ciudades, paquetes, empresas)
- **Anti-duplicados**: dedup batch antes de INSERT y log de inyección previo
- **Hallazgos por ejecución**: resumen en consola al terminar cada opción y un libro Excel por tipo de hallazgo en `logs/<opcion>/<fecha>/` (ADR-014)
- **VERIFICAR**: nunca crea clientes automáticamente en Odoo; marca para revisión manual

## Arquitectura

Arquitectura Hexagonal (Ports & Adapters):

```
src/<módulo>/
├── domain/entities/       # Dataclasses
├── domain/repositories/   # Interfaces (ABC)
├── application/use_cases/ # Lógica de negocio
└── infrastructure/        # Adaptadores (BD, consola, scrapers, XML-RPC)
```

### Módulos

`scrapping` · `billers` · `company` · `rates` · `assign` · `preInvoice` · `odooInjection` · `package` · `provider` · `special` · `city` · `cup` · `activity`

## Stack Tecnológico

| Categoría | Tecnología |
|-----------|-----------|
| Procesamiento de datos | Polars, fastexcel (calamine) |
| Excel I/O | openpyxl, xlsxwriter |
| Web Scraping | Playwright (Firefox), BeautifulSoup |
| Base de datos | PostgreSQL, SQLAlchemy 2.0, Alembic |
| Integración ERP | XML-RPC (Odoo 14 / Avancys) |
| Fuzzy matching | RapidFuzz, Unidecode |
| CLI | Rich |
| Logging | logging + RichHandler (consola) + libros de hallazgos (Polars/xlsxwriter) |
| Testing | pytest + fakes manuales (834 tests) |

## Tests

```bash
pip install -r requirements-dev.txt   # requirements.txt + pytest
pytest
pytest tests/assign/ -v   # Módulo específico
```

La suite incluye guardianes: `tests/test_no_duplicate_test_names.py` (nombres de test duplicados), `tests/test_dead_code_removed.py` (código eliminado) y `tests/docs/` (contenido de la documentación).

## Documentación

- [Guía de Usuario](docs/USER_GUIDE.md)
- [Documentación Técnica](docs/TECHNICAL_DOCUMENTATION.md)
- [Diagramas C4](docs/c4-diagrams.md)
- [ADRs (Decisiones Arquitectónicas)](docs/adr/README.md)
