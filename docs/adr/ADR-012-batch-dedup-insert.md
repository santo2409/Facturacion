# ADR-012: Deduplicación en Memoria antes de INSERT ON CONFLICT

## Estado
Aceptado

## Fecha
2026-06-05

## Contexto

PostgreSQL rechaza un `INSERT ... ON CONFLICT DO UPDATE` cuando el mismo batch contiene filas duplicadas en la clave de conflicto (`CardinalityViolation`). Esto ocurre frecuentemente porque:
- Un mismo NIT aparece múltiples veces en el Excel (varias filas por empresa)
- Tarifas con la misma combinación (contrato + ciudad + CUP + actividad) se repiten en la hoja

Alternativas evaluadas:
1. Insertar fila por fila (lento: N transacciones individuales)
2. Deduplicar en el DataFrame con Polars antes de construir el batch
3. Deduplicar en memoria con dict al construir el batch (último gana)
4. Dividir en sub-batches y reintentar con manejo de excepción

## Decisión

Se deduplica en memoria usando un `dict` con la clave de conflicto como key:

```python
# Rates: clave compuesta de 5 campos
unique = {}
for r in rates_batch:
    key = (r.rateable_id, r.city_id, r.cup_id, r.activity_id, r.rateable_type)
    unique[key] = r
self.rates_repo.save_batch(list(unique.values()))

# Biller-Company: clave simple
unique_links = {}
for company_id, biller_id in link_pairs:
    unique_links[company_id] = biller_id
```

**Política**: último valor gana. Los duplicados omitidos se registran en el log técnico.

## Consecuencias

### Positivas
- Elimina el error `CardinalityViolation` de raíz
- Mantiene el rendimiento de batch insert (una transacción)
- Simple y predecible (dict natural de Python)
- Los duplicados omitidos quedan registrados para auditoría

### Negativas
- Si los duplicados tienen valores diferentes, solo se conserva el último
- La detección de duplicados consume memoria proporcional al batch
