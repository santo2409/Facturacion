# Documentación Técnica - Sistema de Facturación SOANDES

## 1. Información General

| Campo | Valor |
|-------|-------|
| **Nombre del Proyecto** | Facturación SOANDES |
| **Versión de Python** | 3.12 |
| **Tipo de Aplicación** | CLI (Command Line Interface) |
| **Base de Datos** | PostgreSQL |
| **Patrón Arquitectónico** | Arquitectura Hexagonal / Clean Architecture |
| **ORM** | SQLAlchemy 2.0 |
| **Migraciones** | Alembic |
| **ERP Destino** | Odoo 14 (Avancys) — inyección de facturas via XML-RPC |

## 2. Descripción del Sistema

Sistema de facturación para SOANDES que automatiza el proceso de:
1. **Web Scraping** de NITs en el RUES (Registro Único Empresarial y Social)
2. **Importación y normalización** de datos desde archivos Excel
3. **Gestión de facturadores**, empresas, tarifas, paquetes y proveedores
4. **Asignación de tarifas** a empresas según reglas de negocio (cascada de resolución)
5. **Generación de pre-facturas** separadas por NIT
6. **Inyección de facturas** en Odoo/Avancys via XML-RPC con lógica anti-duplicados

## 3. Stack Tecnológico

### Lenguaje y Runtime
- **Python 3.12** con tipado estático (dataclasses, type hints)

### Procesamiento de Datos
- **Polars** — DataFrame library de alto rendimiento para ETL
- **openpyxl** — Lectura de archivos Excel (.xlsx)
- **xlsxwriter** — Escritura de archivos Excel con formato
- **fastexcel (calamine)** — Motor de lectura rápida de Excel

### Web Scraping
- **Playwright** (Firefox headless) — Automatización de navegador para RUES
- **BeautifulSoup4** — Parsing de HTML

### Base de Datos
- **PostgreSQL** — Base de datos relacional
- **SQLAlchemy 2.0** — ORM y gestión de conexiones
- **psycopg2-binary** — Driver PostgreSQL
- **Alembic** — Migraciones de esquema

### Integración ERP
- **XML-RPC** (xmlrpc.client) — Comunicación con Odoo 14 (Avancys)
- URL: `https://soandesv14.avancyserp.com`
- BD: `soandesv14`

### Matching y Normalización
- **RapidFuzz** — Fuzzy string matching para nombres de empresas/facturadores
- **Unidecode** — Normalización de caracteres Unicode a ASCII

### Interfaz de Usuario
- **Rich** — Terminal UI con tablas, progreso y colores

### Testing
- **pytest** — Framework de testing (194 tests)
- **Fakes manuales** — Implementaciones in-memory de repositorios

### Logging
- **logging** (stdlib) — Sistema de logging dual (usuario + técnico)
- **ExcelAuditHandler** — Handler custom que escribe auditoría a `user_audit.xlsx`
- **YAML specs** — Configuración declarativa de loggers

### Calidad de Código
- **cspell** — Spell checking para código
- **EditorConfig** — Consistencia de formato

## 4. Arquitectura del Sistema

### 4.1 Patrón Arquitectónico

El proyecto implementa **Arquitectura Hexagonal** (Ports & Adapters) con la siguiente estructura por módulo:

```
src/<módulo>/
├── domain/
│   ├── entities/       # Entidades de dominio (dataclasses)
│   └── repositories/   # Puertos (interfaces ABC)
├── application/
│   └── use_cases/      # Lógica de negocio
└── infrastructure/
    ├── persistence/    # Adaptadores de BD (SQLAlchemy)
    ├── console/        # Controladores CLI
    ├── odoo/           # Adaptadores XML-RPC (módulo odooInjection)
    └── reporting/      # Generadores de reportes
```

### 4.2 Módulos del Sistema

| Módulo | Responsabilidad |
|--------|----------------|
| `scrapping` | Web scraping de NITs en RUES (por NIT y por nombre) |
| `billers` | Gestión de facturadores y vinculación con empresas |
| `company` | Gestión de empresas y sus relaciones con paquetes |
| `rates` | Importación de tarifas con dedup y fuzzy city resolution |
| `dataProcessing` | Normalización de datos desde Excel |
| `assign` | Asignación de tarifas con cascada de resolución de empresas |
| `preInvoice` | Generación de pre-facturas por NIT |
| `odooInjection` | Inyección de facturas en Odoo/Avancys via XML-RPC |
| `package` | Gestión de paquetes de servicios |
| `provider` | Gestión de proveedores |
| `special` | Gestión de tarifas especiales (con rename por año) |
| `city` | Catálogo de ciudades |
| `cup` | Catálogo de CUPS (procedimientos médicos) |
| `activity` | Tipos de actividad (INTRA/EXTRA) |

### 4.3 Módulo Compartido (`shared`)

```
src/shared/
├── database/       # Conexión BD, modelos SQLAlchemy
├── excel/          # Carga y exportación de Excel
├── console/        # Inputs/outputs de consola
├── logging/        # Sistema de logging dual + ExcelAuditHandler
└── utils/          # Utilidades (normalización, fuzzy matching)
```

## 5. Modelo de Datos

### 5.1 Diagrama Entidad-Relación

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   companies     │     │  companies_billers   │     │    billers      │
├─────────────────┤     ├──────────────────────┤     ├─────────────────┤
│ id (PK)         │◄────│ company_id (FK, PK)  │     │ id (PK)         │
│ nit (UNIQUE)    │     │ biller_id (PK)       │────►│ name (UNIQUE)   │
│ name            │     └──────────────────────┘     └─────────────────┘
│ created_at      │
│ updated_at      │     ┌──────────────────────┐     ┌─────────────────┐
└─────────────────┘     │ companies_packages   │     │    packages     │
        │               ├──────────────────────┤     ├─────────────────┤
        └──────────────►│ company_id (FK, PK)  │     │ id (PK)         │
                        │ package_id (PK)      │────►│ name (UNIQUE)   │
                        │ model (PK)           │     └─────────────────┘
                        └──────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│     rates       │     │     cities      │     │ type_activities  │
├─────────────────┤     ├─────────────────┤     ├──────────────────┤
│ rateable_id(PK) │     │ id (PK)         │     │ id (PK)          │
│ city_id (PK)    │────►│ name (UNIQUE)   │     │ name (INTRA/     │
│ cup_id (PK)     │     └─────────────────┘     │      EXTRA)      │
│ rate            │                              └──────────────────┘
│ activity_id(PK) │     ┌─────────────────┐
│ rateable_type(PK│     │      cups       │
└─────────────────┘────►├─────────────────┤
                        │ id (PK)         │
                        │ code (UNIQUE)   │
                        │ name (UNIQUE)   │
                        └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   providers     │     │    specials     │     │      tian       │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id (PK)         │     │ id (PK)         │     │ nit_error (PK)  │
│ name (UNIQUE)   │     │ name (UNIQUE)   │     │ name            │
└─────────────────┘     └─────────────────┘     └─────────────────┘

┌─────────────────┐
│    imedical     │
├─────────────────┤
│ nit_error (PK)  │
│ name            │
│ nit_success     │
└─────────────────┘
```

### 5.2 Tabla de Tarifas (rates)

La tabla `rates` usa una **clave primaria compuesta** de 5 campos que permite almacenar tarifas polimórficas:
- `rateable_id` + `rateable_type`: Referencia polimórfica (Package, Provider, Special)
- `city_id`: Ciudad donde aplica la tarifa
- `cup_id`: Procedimiento médico (CUPS)
- `activity_id`: Tipo de actividad (INTRA/EXTRA)

## 6. Flujo de Negocio Principal

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE FACTURACIÓN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Web Scrapping (RUES)                                        │
│     └─► Validar NITs de empresas (por NIT y por nombre)         │
│                                                                 │
│  2. Cargar Facturadores                                         │
│     └─► Importar desde Excel → BD (dedup por company_id)        │
│                                                                 │
│  3. Tratamiento de Información                                  │
│     └─► Normalizar Paquetes, Proveedores, Tarifas Especiales   │
│                                                                 │
│  4. Cargar Tarifas                                              │
│     ├─► Importar tarifas desde Excel → BD                       │
│     ├─► Fuzzy city resolution (BOGOTA → BOGOTA D.C)            │
│     ├─► Rename de tarifas especiales (ALQUERIA 2025 → 2026)    │
│     └─► Dedup por clave compuesta antes de INSERT               │
│                                                                 │
│  5. Registrar Empresas - Paquetes                               │
│     └─► Asociar empresas con paquetes y facturadores            │
│                                                                 │
│  6. Asignar Tarifas                                             │
│     ├─► Cascada de resolución de empresas (6 pasos)             │
│     ├─► Normalización de NITs, fechas y sufijos corporativos    │
│     ├─► Cruzar datos con catálogos (fuzzy matching)             │
│     ├─► Calcular totales por procedimiento                      │
│     └─► Generar CONSOLIDADO.xlsx                                │
│                                                                 │
│  7. Generar Pre-Facturas (automático si día < 5 o > 29)        │
│     └─► Separar CONSOLIDADO por NIT → archivos individuales     │
│                                                                 │
│  8. Inyección a Odoo/Avancys (XML-RPC)                          │
│     ├─► Lógica anti-duplicados (lee log previo)                 │
│     ├─► Búsqueda de cliente: NIT (=like) → nombre → VERIFICAR  │
│     └─► Genera log Excel con resultados                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 7. Lógica de Negocio Detallada

### 7.1 Cascada de Resolución de Empresas (`_match_companies`)

Cuando el sistema necesita resolver una empresa a partir de un NIT/nombre del Excel, sigue esta cascada:

| Paso | Fuente | Método | Descripción |
|------|--------|--------|-------------|
| 1 | BD local | NIT | Búsqueda directa por NIT normalizado |
| 2 | BD local | Nombre | Búsqueda por nombre normalizado (corrige NIT erróneo) |
| 3 | RUES | NIT | Web scraping por NIT (cacheado por sesión) |
| 4 | RUES | Nombre | Web scraping por nombre via `search_by_name` (cacheado) |
| 5 | Odoo | NIT | XML-RPC `find_client` con patrón `=like` para DV (cacheado) |
| 6 | Odoo | Nombre | XML-RPC `find_client_by_name` + `get_nit` (cacheado) |
| 7 | Fallback | — | Log `[NOVEDAD]`, se mantienen valores originales |

Cada cambio se anota con la fuente: `[BD local]`, `[RUES/NIT]`, `[Odoo/nombre]`, etc.

### 7.2 Normalización de NITs

```python
# Elimina todo caracter no numérico y toma los primeros 9 dígitos
nit = re.sub(r"[^\d]", "", str(nit_raw).strip())[:9]
```

Formatos soportados: `899.999.063`, `89999906-3`, `899999063-7`, `CO899999063`.

### 7.3 Normalización de Fechas

- Parseo de formatos `dd/mm/yyyy` y `yyyy-mm-dd`
- **Smart swap**: si la fecha excede el periodo de facturación y el día ≤ 12, se intenta intercambio día/mes
- El swap solo se acepta si el resultado cae dentro del mes de trabajo
- Advertencias para fechas > 3 meses de antigüedad o futuras
- Salida siempre en formato `dd/mm/yyyy`

### 7.4 Normalización de Sufijos Corporativos

Consolidación regex en la columna "Empresa":
- `S A S` → `SAS`
- `S A` → `SA`
- `L T D A` → `LTDA`
- `E U` → `EU`
- `E S P` → `ESP`

### 7.5 Resolución Fuzzy de Ciudades (Opción 4)

Cuando una ciudad del Excel no existe en el catálogo BD (ej: "BOGOTA" vs "BOGOTA D.C"):
1. Se construye un `city_alias` map con fuzzy matching (threshold=90%)
2. `fuzz_property` prueba `token_sort_ratio` y luego `partial_ratio`
3. `partial_ratio` resuelve casos como "LA DORADA CALDAS" → "LA DORADA" (score 100%)

### 7.6 Rename de Tarifas Especiales

Las tarifas especiales se renombran in-place cuando el Excel trae un nombre similar con año diferente:
- Ejemplo: "ALQUERIA 2025" en BD + "ALQUERIA 2026" en Excel → se renombra el registro existente
- Se usa `_resolve_names_with_renames()` con threshold=95%
- El `id` se mantiene, por lo que las tarifas asociadas siguen siendo válidas
- Los paquetes normales NO se renombran: pueden coexistir "PAQUETE 1 2024" y "PAQUETE 1 2025"

### 7.7 Deduplicación Batch antes de INSERT

PostgreSQL rechaza `INSERT ... ON CONFLICT DO UPDATE` cuando el mismo batch tiene filas duplicadas en la clave de conflicto. El sistema deduplica:
- **Rates**: por `(rateable_id, city_id, cup_id, activity_id, rateable_type)` — último valor gana
- **Biller-Company links**: por `company_id` — último valor gana, duplicados se registran en logs

### 7.8 Inyección de Facturas a Odoo (Anti-duplicados)

1. Lee log previo (`log_inyeccion.xlsx`) para obtener NITs ya procesados con status "OK"
2. Filtra empresas ya procesadas del batch actual
3. Busca cliente en Odoo: NIT (`=like` para cobertura DV) → nombre (strip sufijo + ilike)
4. Si no encuentra: marca como **VERIFICAR** (nunca crea clientes automáticamente)
5. Genera log Excel con resultados de la inyección

### 7.9 Búsqueda de Cliente en Odoo

```python
# Paso 1: búsqueda exacta por NIT
["vat", "=", nit]

# Paso 2: búsqueda con patrón =like (cubre DV)
["vat", "=like", f"{nit}%"]

# Paso 3: búsqueda por nombre (strip sufijo + ilike)
["name", "ilike", f"%{base_name}%"]
```

## 8. Configuración del Entorno

### Variables de Entorno Requeridas

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_DB_USER` | Usuario de la base de datos |
| `SUPABASE_DB_PASSWORD` | Contraseña de la base de datos |
| `SUPABASE_DB_HOST` | Host del servidor PostgreSQL |
| `SUPABASE_DB_PORT` | Puerto (default: 5432) |
| `SUPABASE_DB_NAME` | Nombre de la BD (default: postgres) |
| `DIRECTORY` | Directorio de trabajo para archivos Excel y logs |
| `ODOO_URL` | URL de Odoo/Avancys |
| `ODOO_DB` | Base de datos de Odoo |
| `ODOO_USER` | Usuario de Odoo |
| `ODOO_PASSWORD` | Contraseña de Odoo |

### Instalación

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirement.txt
playwright install firefox
```

### Ejecución

```bash
python main.py
```

### Migraciones

```bash
alembic upgrade head        # Aplicar migraciones
alembic revision --autogenerate -m "descripción"  # Nueva migración
```

## 9. Testing

### Estrategia de Testing

- **Unit Tests** con pytest (194 tests)
- **Fakes manuales** (implementaciones in-memory de repositorios)
- No se usan mocks de librería; se prefieren fakes explícitos

### Ejecución de Tests

```bash
pytest                      # Todos los tests
pytest tests/assign/        # Tests de un módulo
pytest -v                   # Verbose
```

### Estructura de Fakes

```
tests/fakes/
├── fake_biller_repo.py
├── fake_company_repo.py
├── fake_rates_repo.py
├── fake_package_repo.py
├── fake_provider_repo.py
├── fake_special_repo.py
├── fake_city_repo.py
├── fake_activity_repo.py
├── fake_cup_repo.py
├── fake_nit_service.py        # Incluye search_by_name
├── fake_odoo_repo.py          # find_client_by_name, get_nit
├── fake_biller_company_repo.py
├── fake_log_generator.py      # read_successful_nits
├── fake_progress.py
├── fake_fuzz.py
└── fake_logger.py
```

## 10. Sistema de Logging

El sistema implementa un **logging dual**:

1. **User Logger** (`logs/user_audit.xlsx`): Mensajes orientados al usuario final con contexto de negocio, en formato Excel con colores por nivel.
2. **Tech Logger** (`logs/logs.log`): Mensajes técnicos para debugging con stack traces.

### ExcelAuditHandler

Handler custom que:
- Acumula registros en memoria durante la ejecución
- Al finalizar el proceso (`atexit`), escribe todos los registros a `user_audit.xlsx`
- Aplica colores: azul (INFO), amarillo (WARNING), rojo (ERROR/CRITICAL)
- Header congelado con anchos de columna y bordes

### Configuración

Declarativa via YAML (`spec/user_logger.yaml`) con validación y guard contra mutación del root logger.

### Uso desde Código

```python
# Log a ambos (técnico + auditoría usuario)
logger.error(
    f"Error técnico: {exception}",
    exc_info=True,
    user_msg="No se pudo procesar el archivo."
)

# Log solo a tech_logger (sin mostrar en consola ni auditoría)
import logging
logging.getLogger("tech_logger").warning(msg)
logging.getLogger("user_logger").warning(msg)
```

## 11. Convenciones del Proyecto

- **Entidades**: `dataclass` simples sin lógica
- **Repositorios**: Clases abstractas (ABC) como puertos
- **Use Cases**: Una clase por caso de uso con método `execute()`
- **Controllers**: Orquestan la inyección de dependencias y la interacción con consola
- **Naming**: camelCase para módulos, snake_case para archivos Python
- **Imports**: Absolutos desde `src/`
- **Batch operations**: Siempre deduplicar antes de `INSERT ON CONFLICT`
- **Odoo**: Nunca crear clientes automáticamente, marcar como VERIFICAR
- **Dates**: Formato de salida siempre `dd/mm/yyyy`
- **NITs**: Siempre normalizar a 9 dígitos sin separadores
