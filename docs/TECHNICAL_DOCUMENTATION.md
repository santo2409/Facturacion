# Documentación Técnica - Sistema de Facturación SOANDES

## 1. Información General

| Campo | Valor |
|-------|-------|
| **Nombre del Proyecto** | Facturación SOANDES |
| **Versión de Python** | 3.12 |
| **Tipo de Aplicación** | CLI (Command Line Interface) |
| **Base de Datos** | PostgreSQL (Supabase) |
| **Patrón Arquitectónico** | Arquitectura Hexagonal / Clean Architecture |
| **ORM** | SQLAlchemy 2.0 |
| **Migraciones** | Alembic |

## 2. Descripción del Sistema

Sistema de facturación para SOANDES que automatiza el proceso de:
1. **Web Scraping** de NITs en el RUES (Registro Único Empresarial y Social)
2. **Importación y normalización** de datos desde archivos Excel
3. **Gestión de facturadores**, empresas, tarifas, paquetes y proveedores
4. **Asignación de tarifas** a empresas según reglas de negocio
5. **Generación de pre-facturas** separadas por NIT

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
- **PostgreSQL** (Supabase) — Base de datos relacional en la nube
- **SQLAlchemy 2.0** — ORM y gestión de conexiones
- **psycopg2-binary** — Driver PostgreSQL
- **Alembic** — Migraciones de esquema

### Matching y Normalización
- **RapidFuzz** — Fuzzy string matching para nombres de empresas/facturadores
- **Unidecode** — Normalización de caracteres Unicode a ASCII

### Interfaz de Usuario
- **Rich** — Terminal UI con tablas, progreso y colores

### Testing
- **pytest** — Framework de testing
- **Fakes manuales** — Implementaciones in-memory de repositorios

### Logging
- **logging** (stdlib) — Sistema de logging dual (usuario + técnico)
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
    └── console/        # Controladores CLI
```

### 4.2 Módulos del Sistema

| Módulo | Responsabilidad |
|--------|----------------|
| `scrapping` | Web scraping de NITs en RUES |
| `billers` | Gestión de facturadores |
| `company` | Gestión de empresas y sus relaciones |
| `rates` | Importación y gestión de tarifas |
| `dataProcessing` | Normalización de datos desde Excel |
| `assign` | Asignación de tarifas a empresas |
| `preInvoice` | Generación de pre-facturas por NIT |
| `package` | Gestión de paquetes de servicios |
| `provider` | Gestión de proveedores |
| `special` | Gestión de tarifas especiales |
| `city` | Catálogo de ciudades |
| `cup` | Catálogo de CUPS (procedimientos médicos) |
| `activity` | Tipos de actividad (INTRA/EXTRA) |

### 4.3 Módulo Compartido (`shared`)

```
src/shared/
├── database/       # Conexión BD, modelos SQLAlchemy
├── excel/          # Carga y exportación de Excel
├── console/        # Inputs/outputs de consola
├── logging/        # Sistema de logging dual
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
- `rateable_id` + `rateable_type`: Referencia polimórfica (package, provider, special)
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
│     └─► Validar NITs de empresas                                │
│                                                                 │
│  2. Cargar Facturadores                                         │
│     └─► Importar desde Excel → BD                               │
│                                                                 │
│  3. Tratamiento de Información                                  │
│     └─► Normalizar Paquetes, Proveedores, Tarifas Especiales   │
│                                                                 │
│  4. Cargar Tarifas                                              │
│     └─► Importar tarifas desde Excel → BD                       │
│                                                                 │
│  5. Registrar Empresas - Paquetes                               │
│     └─► Asociar empresas con paquetes y facturadores            │
│                                                                 │
│  6. Asignar Tarifas                                             │
│     ├─► Cruzar datos con catálogos (fuzzy matching)             │
│     ├─► Calcular totales por procedimiento                      │
│     └─► Generar CONSOLIDADO.xlsx                                │
│                                                                 │
│  7. Generar Pre-Facturas (automático si día < 5 o > 29)        │
│     └─► Separar CONSOLIDADO por NIT → archivos individuales     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 7. Configuración del Entorno

### Variables de Entorno Requeridas

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_DB_USER` | Usuario de la base de datos |
| `SUPABASE_DB_PASSWORD` | Contraseña de la base de datos |
| `SUPABASE_DB_HOST` | Host de Supabase |
| `SUPABASE_DB_PORT` | Puerto (default: 5432/6543) |
| `SUPABASE_DB_NAME` | Nombre de la BD (default: postgres) |
| `DIRECTORY` | Directorio para logs técnicos |

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

## 8. Testing

### Estrategia de Testing

- **Unit Tests** con pytest
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
├── fake_nit_service.py
├── fake_biller_company_repo.py
├── fake_progress.py
├── fake_fuzz.py
└── fake_logger.py
```

## 9. Sistema de Logging

El sistema implementa un **logging dual**:

1. **User Logger** (`user_audit.log`): Mensajes orientados al usuario final con contexto de negocio
2. **Tech Logger** (`logs.log`): Mensajes técnicos para debugging con stack traces

Configurado mediante YAML specs con validación y guardas contra mutación del root logger.

## 10. Convenciones del Proyecto

- **Entidades**: `dataclass` simples sin lógica
- **Repositorios**: Clases abstractas (ABC) como puertos
- **Use Cases**: Una clase por caso de uso con método `execute()`
- **Controllers**: Orquestan la inyección de dependencias y la interacción con consola
- **Naming**: camelCase para módulos, snake_case para archivos Python
- **Imports**: Absolutos desde `src/`
