# ADR-007: Rich como Framework de Interfaz CLI

## Estado
Aceptado

## Fecha
2024-12-13

## Contexto

El sistema opera como aplicación de línea de comandos interactiva. Se necesita:
- Menú de opciones navegable
- Barras de progreso para operaciones largas (scraping, importación)
- Feedback visual con colores para estados (éxito, error, advertencia)
- Tablas formateadas para mostrar información

Alternativas evaluadas:
1. `print()` con ANSI codes manuales
2. Click — Framework CLI con decoradores
3. Rich — Librería de terminal enriquecida
4. Textual — TUI completa (del mismo autor de Rich)

## Decisión

Se adopta **Rich** para toda la interacción con el usuario:
- `Console` para output con formato
- `Prompt` para input interactivo
- `Table` para menús y datos tabulares
- `Progress` / `track` para barras de progreso
- Abstracción `RichProgress` como wrapper inyectable

## Consecuencias

### Positivas
- Output visualmente atractivo sin complejidad
- Barras de progreso informativas para operaciones largas
- API simple y bien documentada
- No requiere configuración de terminal especial

### Negativas
- Dependencia adicional para funcionalidad que podría ser básica
- Output no es fácilmente parseable por scripts externos
- La abstracción `RichProgress` añade una capa de indirección

## Notas
`RichProgress` se inyecta como dependencia en los casos de uso, permitiendo sustituirla por `FakeProgress` en tests sin output real a terminal.
