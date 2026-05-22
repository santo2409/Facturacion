# ADR-002: PostgreSQL en Supabase como Base de Datos

## Estado
Aceptado

## Fecha
2025-02-21

## Contexto

El sistema necesita una base de datos relacional para almacenar catálogos (empresas, facturadores, tarifas, CUPS, ciudades) y relaciones entre entidades. Inicialmente se usó MySQL, pero se requería:
- Hosting gestionado sin administración de infraestructura
- Conexión segura (SSL) desde la aplicación local
- Soporte para claves primarias compuestas y constraints complejos
- Escalabilidad sin costo operativo elevado

Alternativas evaluadas:
1. MySQL local/RDS
2. PostgreSQL en Supabase
3. SQLite local

## Decisión

Se migra a **PostgreSQL hospedado en Supabase** con:
- Conexión vía `psycopg2-binary` con SSL (`sslmode=require`)
- ORM SQLAlchemy 2.0 con `declarative_base`
- Migraciones gestionadas con Alembic
- Connection pooling con `pool_pre_ping=True`

## Consecuencias

### Positivas
- Hosting gestionado con backups automáticos
- Dashboard web para inspección de datos
- API REST automática (no utilizada actualmente pero disponible)
- Soporte nativo para constraints CHECK, UNIQUE compuestos
- Tier gratuito suficiente para el volumen actual

### Negativas
- Dependencia de un proveedor cloud (vendor lock-in mitigado por SQLAlchemy)
- Latencia de red vs base de datos local
- Requiere conexión a internet para operar
- Credenciales sensibles en `.env` (no versionado)

## Notas
La URL de conexión se construye dinámicamente desde variables de entorno, permitiendo apuntar a diferentes instancias (desarrollo, producción) sin cambios en código.
