# ADR-009: Lógica Anti-Duplicados en Inyección de Facturas

## Estado
Aceptado

## Fecha
2026-06-05

## Contexto

Al inyectar facturas en Odoo/Avancys via XML-RPC, el proceso puede interrumpirse por errores de red, timeouts o fallos parciales. Al re-ejecutar, se correría el riesgo de duplicar facturas ya creadas exitosamente.

Alternativas evaluadas:
1. Verificar cada factura en Odoo antes de crearla (lento: N llamadas XML-RPC)
2. Mantener un log local de resultados y filtrar al re-ejecutar
3. Usar campo unique en Odoo para rechazar duplicados (requiere cambios en Odoo)

## Decisión

Se implementa un **log Excel local** (`log_inyeccion.xlsx`) que registra el resultado de cada inyección:
- `ExcelLogGenerator.read_successful_nits(path)` lee los NITs con status "OK" del log previo
- Antes de procesar, se filtran empresas ya inyectadas exitosamente
- El log se reescribe completo en cada ejecución (append de nuevos resultados)

## Consecuencias

### Positivas
- Re-ejecución segura sin duplicar facturas
- No requiere cambios en Odoo
- El operador puede ver el historial de inyecciones en Excel
- Rendimiento óptimo: una sola lectura de archivo vs N llamadas XML-RPC

### Negativas
- Si se borra el log manualmente, se pierden los registros de lo ya inyectado
- No protege contra duplicados si se ejecuta desde otra máquina sin el log
- El log crece con cada ejecución mensual
