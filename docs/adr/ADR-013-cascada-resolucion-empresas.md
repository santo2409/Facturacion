# ADR-013: Cascada de Resolución de Empresas (6 Fuentes)

## Estado
Aceptado

## Fecha
2026-06-05

## Contexto

Los archivos Excel de entrada frecuentemente contienen datos de empresa incorrectos: NITs con formato erróneo, nombres desactualizados o empresas no registradas en la BD local. Se necesita un mecanismo robusto para resolver la empresa correcta antes de asignar tarifas.

Fuentes de verdad disponibles:
1. BD local (PostgreSQL) — catálogo de empresas conocidas
2. RUES — registro oficial colombiano (web scraping)
3. Odoo/Avancys — ERP con datos de clientes activos

Alternativas evaluadas:
1. Solo BD local (falla con empresas nuevas)
2. Solo RUES (lento para todas las filas)
3. Cascada progresiva: empezar por la fuente más rápida y barata

## Decisión

Se implementa una **cascada de 6 pasos** que consulta fuentes de menor a mayor costo:

| Paso | Fuente | Búsqueda | Costo |
|------|--------|----------|-------|
| 1 | BD local | NIT | ~0ms (dict in-memory) |
| 2 | BD local | Nombre | ~0ms (dict in-memory) |
| 3 | RUES | NIT | ~2-5s (web scraping) |
| 4 | RUES | Nombre | ~2-5s (web scraping) |
| 5 | Odoo | NIT (`=like`) | ~200ms (XML-RPC) |
| 6 | Odoo | Nombre (ilike) | ~200ms (XML-RPC) |

Optimizaciones:
- Cache por sesión: cada NIT/nombre se consulta una sola vez por fuente externa
- Retry con delay de 5s para RUES (max 3 intentos)
- Los cambios aplicados se anotan con la fuente: `[BD local]`, `[RUES/NIT]`, `[Odoo/nombre]`

## Consecuencias

### Positivas
- Alta tasa de resolución (>95% de empresas se resuelven)
- Mínimo impacto en rendimiento (la mayoría se resuelve en pasos 1-2)
- Trazabilidad completa de la fuente de cada corrección
- Cache evita consultas redundantes

### Negativas
- Complejidad del código de resolución
- Dependencia de disponibilidad de RUES y Odoo
- Si RUES está caído, los pasos 3-4 fallan silenciosamente (se loguea y continúa)
