# ADR-001: Adopción de Arquitectura Hexagonal (Ports & Adapters)

## Estado
Aceptado

## Fecha
2024-12-14

## Contexto

El sistema de facturación SOANDES requiere:
- Integración con múltiples fuentes de datos (Excel, web scraping, base de datos)
- Capacidad de cambiar proveedores de infraestructura sin afectar la lógica de negocio
- Testabilidad independiente de la base de datos y servicios externos
- Separación clara entre reglas de negocio y detalles técnicos

Se evaluaron las siguientes alternativas:
1. Arquitectura en capas tradicional (MVC)
2. Arquitectura Hexagonal / Clean Architecture
3. Arquitectura basada en eventos

## Decisión

Se adopta **Arquitectura Hexagonal** (Ports & Adapters) con la siguiente estructura por módulo:

```
módulo/
├── domain/          # Núcleo: entidades + puertos (ABC)
├── application/     # Casos de uso
└── infrastructure/  # Adaptadores (BD, consola, scrapers)
```

- **Puertos**: Interfaces abstractas (ABC) en `domain/repositories/`
- **Adaptadores**: Implementaciones concretas en `infrastructure/`
- **Entidades**: Dataclasses puras sin dependencias externas

## Consecuencias

### Positivas
- Los casos de uso son testeables con fakes in-memory sin necesidad de BD real
- Se puede migrar de MySQL a PostgreSQL (Supabase) cambiando solo los adaptadores
- La lógica de negocio está aislada de frameworks y librerías externas
- Facilita la incorporación de nuevos módulos siguiendo el mismo patrón

### Negativas
- Mayor cantidad de archivos y directorios por módulo
- Curva de aprendizaje para desarrolladores no familiarizados con el patrón
- Overhead de abstracción para módulos simples (ej: `city`, `cup`)

## Notas
El proyecto evidencia la migración exitosa de MySQL a PostgreSQL/Supabase, validando la decisión de desacoplar la persistencia del dominio.
