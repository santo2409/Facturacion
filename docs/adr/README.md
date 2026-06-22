# Architecture Decision Records (ADRs)

Registro de decisiones arquitectónicas del proyecto de Facturación SOANDES.

## Índice

| # | Título | Estado | Fecha |
|---|--------|--------|-------|
| [ADR-001](ADR-001-arquitectura-hexagonal.md) | Arquitectura Hexagonal (Ports & Adapters) | Aceptado | 2024-12-14 |
| [ADR-002](ADR-002-postgresql-supabase.md) | PostgreSQL en Supabase | Aceptado | 2025-02-21 |
| [ADR-003](ADR-003-polars-procesamiento-datos.md) | Polars como Motor de Procesamiento | Aceptado | 2024-12-13 |
| [ADR-004](ADR-004-playwright-web-scraping.md) | Playwright para Web Scraping | Aceptado | 2024-12-14 |
| [ADR-005](ADR-005-testing-fakes-manuales.md) | Testing con Fakes Manuales | Aceptado | 2024-12-14 |
| [ADR-006](ADR-006-rapidfuzz-matching-difuso.md) | RapidFuzz para Matching Difuso | Aceptado | 2024-12-13 |
| [ADR-007](ADR-007-rich-cli-framework.md) | Rich como Framework CLI | Aceptado | 2024-12-13 |
| [ADR-008](ADR-008-logging-dual.md) | Sistema de Logging Dual | Aceptado | 2024-12-17 |
| [ADR-009](ADR-009-anti-duplicados-inyeccion.md) | Anti-Duplicados en Inyección de Facturas | Aceptado | 2026-06-05 |
| [ADR-010](ADR-010-verificar-no-crear-cliente.md) | VERIFICAR en Lugar de Crear Clientes en Odoo | Aceptado | 2026-06-05 |
| [ADR-011](ADR-011-excel-audit-handler.md) | ExcelAuditHandler para Auditoría | Aceptado | 2026-06-05 |
| [ADR-012](ADR-012-batch-dedup-insert.md) | Deduplicación antes de INSERT ON CONFLICT | Aceptado | 2026-06-05 |
| [ADR-013](ADR-013-cascada-resolucion-empresas.md) | Cascada de Resolución de Empresas | Aceptado | 2026-06-05 |

## Formato

Cada ADR sigue la estructura:
- **Estado**: Propuesto / Aceptado / Deprecado / Reemplazado
- **Contexto**: Problema y alternativas evaluadas
- **Decisión**: Qué se decidió y por qué
- **Consecuencias**: Impacto positivo y negativo
