# Facturación SOANDES

Sistema CLI para automatizar el proceso de facturación de SOANDES: importación de datos desde Excel, validación de NITs, asignación de tarifas, generación de pre-facturas e inyección de facturas en Odoo/Avancys.

## Requisitos

- Python 3.12+
- PostgreSQL
- Firefox (para web scraping RUES)
- Acceso a Odoo 14 / Avancys (para inyección de facturas)

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
SUPABASE_DB_HOST=tu_host
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
DIRECTORY=.

# Odoo / Avancys
ODOO_URL=https://soandesv14.avancyserp.com
ODOO_DB=soandesv14
ODOO_USER=tu_usuario_odoo
ODOO_PASSWORD=tu_contraseña_odoo
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
| 1 | Web Scrapping | Valida NITs en el RUES (por NIT y por nombre) |
| 2 | Facturadores | Importa facturadores desde Excel y vincula con empresas |
| 3 | Tratamiento Información | Normaliza paquetes, proveedores y tarifas especiales |
| 4 | Cargar Tarifas | Importa tarifas desde Excel a BD (fuzzy city, rename especiales) |
| 5 | Registrar Empresas | Asocia empresas con paquetes y facturadores |
| 6 | Asignar Tarifas | Cascada de resolución, normalización y generación de pre-facturas |
| 7 | Inyectar Facturas | Inyecta facturas en Odoo/Avancys via XML-RPC |

### Flujo típico de facturación

```
1. Web Scrapping → 2. Facturadores → 3. Tratamiento → 4. Tarifas → 5. Empresas → 6. Asignar → 7. Inyectar
```

La opción 6 genera automáticamente las pre-facturas (archivos Excel por NIT) si el día del mes es < 5 o > 29.

La opción 7 incluye lógica anti-duplicados: si se re-ejecuta, no duplica facturas ya inyectadas.

## Características Principales

- **Cascada de resolución de empresas**: BD local → RUES → Odoo (6 pasos)
- **Normalización inteligente**: NITs (9 dígitos), fechas (smart swap dd/mm), sufijos corporativos (S.A.S → SAS)
- **Fuzzy matching**: resolución de nombres con RapidFuzz (ciudades, paquetes, empresas)
- **Anti-duplicados**: dedup batch antes de INSERT y log de inyección previo
- **Auditoría Excel**: log de usuario en `user_audit.xlsx` con colores por nivel
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

`scrapping` · `billers` · `company` · `rates` · `dataProcessing` · `assign` · `preInvoice` · `odooInjection` · `package` · `provider` · `special` · `city` · `cup` · `activity`

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
| Logging | logging + ExcelAuditHandler (user_audit.xlsx) |
| Testing | pytest + fakes manuales (194 tests) |

## Tests

```bash
pytest
pytest tests/assign/ -v   # Módulo específico
```

## Documentación

- [Documentación Técnica](docs/TECHNICAL_DOCUMENTATION.md)
- [Diagramas C4](docs/c4-diagrams.md)
- [ADRs (Decisiones Arquitectónicas)](docs/adr/README.md)
