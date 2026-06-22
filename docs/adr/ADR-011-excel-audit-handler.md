# ADR-011: ExcelAuditHandler para Auditoría de Usuario

## Estado
Aceptado (reemplaza parcialmente ADR-008 en formato de salida)

## Fecha
2026-06-05

## Contexto

El sistema de logging dual (ADR-008) originalmente escribía auditoría de usuario en un archivo `.log` plano. Los operadores:
- Prefieren archivos Excel que pueden filtrar y compartir
- No están familiarizados con archivos `.log`
- Necesitan distinguir visualmente errores de información

Alternativas evaluadas:
1. Mantener `.log` plano con formato legible
2. Migrar a Excel con handler custom
3. Generar PDF de auditoría

## Decisión

Se implementa `ExcelAuditHandler` como handler de logging que:
- Hereda de `logging.Handler`
- Acumula registros en memoria durante la ejecución
- Al finalizar (`atexit`), escribe a `logs/user_audit.xlsx`
- Aplica formato visual: azul (INFO), amarillo (WARNING), rojo (ERROR/CRITICAL)
- Header congelado, anchos de columna y bordes
- Configurado en `user_logger.yaml` como handler del `user_logger`

El `tech_logger` sigue usando `RotatingFileHandler` a `logs/logs.log`.

## Consecuencias

### Positivas
- Los operadores pueden abrir, filtrar y compartir la auditoría en Excel
- Distinción visual inmediata por color de nivel de log
- Compatible con el flujo existente de `LoggerAdapter` (solo cambia el handler)

### Negativas
- Los registros se pierden si el proceso se mata abruptamente (antes del `atexit`)
- Archivo Excel crece por sesión (no tiene rotación como RotatingFileHandler)
- Dependencia de openpyxl para escribir la auditoría
