# Facturación SOANDES

Sistema CLI para automatizar el proceso de facturación de SOANDES: importación de datos desde Excel, validación de NITs, asignación de tarifas y generación de pre-facturas.

## Requisitos

- Python 3.12+
- PostgreSQL (Supabase)
- Firefox (para web scraping)

## Instalación

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirement.txt
playwright install firefox
```

## Configuración

Crear archivo `.env` en la raíz del proyecto:

```env
SUPABASE_DB_USER=tu_usuario
SUPABASE_DB_PASSWORD=tu_contraseña
SUPABASE_DB_HOST=tu_host.supabase.co
SUPABASE_DB_PORT=6543
SUPABASE_DB_NAME=postgres
DIRECTORY=.
```

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
| 1 | Web Scrapping | Valida NITs en el RUES |
| 2 | Facturadores | Importa facturadores desde Excel |
| 3 | Tratamiento Información | Normaliza paquetes, proveedores y tarifas especiales |
| 4 | Cargar Tarifas | Importa tarifas desde Excel a BD |
| 5 | Registrar Empresas | Asocia empresas con paquetes y facturadores |
| 6 | Asignar Tarifas | Cruza datos, calcula tarifas y genera pre-facturas |

### Flujo típico de facturación

```
1. Web Scrapping → 2. Facturadores → 3. Tratamiento → 4. Tarifas → 5. Empresas → 6. Asignar
```

La opción 6 genera automáticamente las pre-facturas (archivos Excel por NIT) si el día del mes es < 5 o > 29.

## Arquitectura

Arquitectura Hexagonal (Ports & Adapters):

```
src/<módulo>/
├── domain/entities/       # Dataclasses
├── domain/repositories/   # Interfaces (ABC)
├── application/use_cases/ # Lógica de negocio
└── infrastructure/        # Adaptadores (BD, consola, scrapers)
```

### Módulos

`scrapping` · `billers` · `company` · `rates` · `dataProcessing` · `assign` · `preInvoice` · `package` · `provider` · `special` · `city` · `cup` · `activity`

## Stack Tecnológico

| Categoría | Tecnología |
|-----------|-----------|
| Procesamiento de datos | Polars, fastexcel (calamine) |
| Excel I/O | openpyxl, xlsxwriter |
| Web Scraping | Playwright (Firefox), BeautifulSoup |
| Base de datos | PostgreSQL/Supabase, SQLAlchemy 2.0, Alembic |
| Fuzzy matching | RapidFuzz, Unidecode |
| CLI | Rich |
| Testing | pytest + fakes manuales |

## Tests

```bash
pytest
pytest tests/assign/ -v   # Módulo específico
```

## Documentación

- [Documentación Técnica](docs/TECHNICAL_DOCUMENTATION.md)
- [Diagramas C4](docs/c4-diagrams.md)
- [ADRs (Decisiones Arquitectónicas)](docs/adr/README.md)
