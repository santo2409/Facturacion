# ADR-006: RapidFuzz para Matching Difuso de Nombres

## Estado
Aceptado

## Fecha
2024-12-13

## Contexto

Los datos de facturación provienen de múltiples fuentes (Excel, RUES, iMedical) donde los nombres de empresas y facturadores presentan inconsistencias:
- Variaciones en mayúsculas/minúsculas
- Caracteres especiales y acentos
- Abreviaciones ("S.A.S" vs "SAS" vs "S.A.S.")
- Errores tipográficos

Se necesita un mecanismo para asociar nombres similares con entidades del catálogo.

Alternativas evaluadas:
1. Comparación exacta (normalizada)
2. FuzzyWuzzy (Python puro)
3. RapidFuzz (implementación en C++)
4. Algoritmos de distancia de edición manuales

## Decisión

Se adopta **RapidFuzz** con estrategia de múltiples scorers:

1. `token_sort_ratio` — Ordena tokens y compara (maneja reordenamiento de palabras)
2. `partial_ratio` — Busca la mejor subcadena coincidente

Threshold de 90% para considerar un match válido. Se combina con `unidecode` para normalizar caracteres Unicode antes de comparar.

## Consecuencias

### Positivas
- 10-100x más rápido que FuzzyWuzzy (implementación en C++)
- API compatible con FuzzyWuzzy (migración trivial)
- Múltiples algoritmos de scoring disponibles
- Threshold configurable por caso de uso

### Negativas
- Dependencia nativa (compilación C++ requerida)
- False positives posibles con threshold bajo
- No distingue entre empresas con nombres genuinamente similares
- Requiere catálogo pre-cargado en memoria

## Notas
La clase `RapidFuzzBiller` encapsula la lógica de matching y es inyectable como dependencia en los casos de uso, permitiendo sustituirla por un `FakeFuzz` en tests.
