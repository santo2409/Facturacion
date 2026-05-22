# ADR-003: Polars como Motor de Procesamiento de Datos

## Estado
Aceptado

## Fecha
2024-12-13

## Contexto

El sistema procesa archivos Excel con miles de registros que requieren:
- Normalización de texto (mayúsculas, eliminación de acentos, trim)
- Joins entre múltiples DataFrames (tarifas, empresas, CUPS)
- Filtrado, agrupación y cálculos agregados
- Exportación a Excel con formato

Alternativas evaluadas:
1. Pandas — Estándar de facto para DataFrames en Python
2. Polars — Librería moderna basada en Rust
3. Procesamiento manual con listas/diccionarios

## Decisión

Se adopta **Polars** como motor principal de procesamiento de datos por:
- Rendimiento superior a Pandas en operaciones de transformación
- API expresiva con encadenamiento de operaciones (`with_columns`, `filter`, `join`)
- Tipado estricto de columnas
- Evaluación lazy disponible para optimización de queries complejos
- Menor consumo de memoria

## Consecuencias

### Positivas
- Procesamiento significativamente más rápido para archivos grandes
- API consistente y predecible
- Integración nativa con `calamine` (motor de lectura Excel rápido)
- Expresiones vectorizadas para normalización de texto (`str.strip_chars()`, `str.to_uppercase()`)

### Negativas
- Ecosistema más pequeño que Pandas (menos tutoriales, menos respuestas en StackOverflow)
- Algunos desarrolladores pueden no estar familiarizados
- Interoperabilidad limitada con librerías que esperan Pandas DataFrames
- Se usa `openpyxl` para escritura con formato avanzado (Polars no soporta estilos)

## Notas
Se combina con `fastexcel` (binding de `calamine` en Rust) para lectura de Excel, logrando tiempos de carga muy superiores a `openpyxl` en modo lectura.
