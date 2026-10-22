# ADR-014: Salida al Usuario por Consola y Libros de Hallazgos por Ejecución

## Estado
Aceptado (reemplaza a [ADR-008](ADR-008-logging-dual.md) y a [ADR-011](ADR-011-excel-audit-handler.md))

## Fecha
2026-10-10

## Contexto

El "logging dual" (ADR-008) y el `ExcelAuditHandler` (ADR-011) enviaban cada `user_msg` a un único archivo, `logs/user_audit.xlsx`, que acumulaba todas las corridas y mezclaba tres tipos de mensaje:
- resúmenes de progreso;
- errores;
- **hallazgos por fila** que alguien debe corregir (una ciudad inexistente, un paquete no encontrado, etc.).

Como todo iba junto, el archivo no servía para repartir los hallazgos a las áreas responsables, y el operador debía abrir un Excel aparte para saber cómo había terminado una opción. Además el handler escribía solo al salir (`atexit`), por lo que una corrida interrumpida perdía todo.

La spec 010 resolvió esto para la opción 6 (libros por fase y resumen en consola). La spec 011 lo extiende a todo el sistema.

Alternativas evaluadas:
1. Mantener `user_audit.xlsx` y filtrarlo por opción.
2. Un libro Excel por opción, con una hoja por tipo de hallazgo.
3. Resumen en consola y un libro por tipo de hallazgo, en una carpeta por ejecución.

## Decisión

Se adopta la alternativa 3. La salida al usuario se divide en tres canales:

1. **Log técnico** (`logs.log`, `RotatingFileHandler`): sin cambios.
2. **Consola Rich**: todo `user_msg` se muestra en la consola con color por nivel. `LoggerAdapter` conserva su firma; `user_msg` significa ahora "mensaje al usuario por consola". Una única instancia `USER_CONSOLE` (`src/shared/console/user_console.py`) la comparten el handler de logging y `RichProgress`, de modo que los mensajes salen por encima de la barra de progreso sin romperla.
3. **Libros de hallazgos por ejecución**: cada tipo de hallazgo se escribe en su propio libro Excel, en `logs/<opcion>/<AAAA-MM-DD_HHMM>/`. El puerto `FindingsWriter` y su implementación `XlsxFindingsWriter` (Polars + xlsxwriter) son compartidos por todas las opciones. No se generan libros vacíos.

Reglas de uso:
- `user_msg` es para resúmenes y errores puntuales. **Nunca** para el detalle por fila de un hallazgo: ese detalle va al libro correspondiente y el log técnico, y la consola muestra un único resumen con el conteo por tipo y la ruta de la carpeta, o "Sin hallazgos.".
- Los libros que ya existían (`empresas_no_encontradas`, `novedades_cups`, `empresas_no_vinculadas`, `empresas_duplicadas`, `empresas_tian`, `odoo-output/log_inyeccion`) conservan su ruta y su comportamiento, incluido el histórico acumulado donde lo hay.
- Los flujos con salida propia (opción 6) pueden envolver sus dependencias compartidas en `TechOnlyLogger`, que descarta `user_msg` para no duplicar mensajes.

```python
# El use case acumula los hallazgos por tipo y los publica al terminar
folder = self.findings_writer.write(self._findings, COLUMNS)   # None si no hay filas
summary = summarize_findings(self._findings, folder)           # "Sin hallazgos." | "Hallazgos en <ruta>: tipo=N."
self.logger.info("Resumen de hallazgos", user_msg=summary)
```

## Consecuencias

### Positivas
- Cada libro se entrega al área que debe corregir ese tipo de hallazgo.
- Cada ejecución queda separada de las anteriores; no hay un archivo que crezca sin límite.
- El operador ve el resultado en consola al terminar cada opción, sin abrir archivos.
- Un único escritor de libros (DRY) y un puerto con su fake para testear sin disco.
- Se elimina el `atexit`: los libros se escriben al terminar la opción, no al cerrar el programa.

### Negativas
- Los mensajes de consola no persisten; solo el log técnico y los libros de hallazgos.
- Cambia el lugar donde se buscan los hallazgos: hay que mirar la carpeta de la ejecución.
- Las ejecuciones en el mismo minuto comparten carpeta y la segunda sobrescribe los libros con el mismo nombre.
- `Fila` en los hallazgos de la opción 4 depende de poder leer el `.xlsx` con `openpyxl`; con otros formatos se numera en secuencia.

## Actualización (spec 020, opción 6)
Los libros de la opción 6 se entregan al área de tarifas, así que agrupan por llave original (una fila por paquete, ciudad, CUP y actividad, con `Nº pacientes` en lugar de datos de paciente), indican la fuente de la tarifa asignada y la ciudad y CUP efectivos, sugieren la acción y traen una hoja `Leyenda`. Las tarifas de Odoo vencidas se asignan y se reportan en `odoo_tarifa_vencida.xlsx`. El escritor genérico acepta hojas extra (`extra_sheets`) sin cambiar a sus demás usuarios.

## Referencias
- Specs 010 (opción 6) y 011 (resto del sistema).
- [ADR-008](ADR-008-logging-dual.md) y [ADR-011](ADR-011-excel-audit-handler.md): reemplazados; se conservan como historia.
