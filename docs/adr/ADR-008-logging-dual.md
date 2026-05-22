# ADR-008: Sistema de Logging Dual (Usuario + Técnico)

## Estado
Aceptado

## Fecha
2024-12-17

## Contexto

El sistema necesita registrar eventos para dos audiencias distintas:
1. **Usuarios finales**: Mensajes de auditoría sobre operaciones realizadas (qué se importó, qué falló)
2. **Desarrolladores**: Mensajes técnicos con stack traces para debugging

Mezclar ambos en un solo log dificulta la lectura para cada audiencia.

Alternativas evaluadas:
1. Un solo logger con niveles (DEBUG para técnico, INFO para usuario)
2. Dos loggers independientes con configuración separada
3. Sistema de logging estructurado (JSON)

## Decisión

Se implementa un **sistema de logging dual** con:
- `LoggerAdapter` como wrapper que acepta `user_msg` opcional
- **User Logger** → `logs/user_audit.log` (RotatingFileHandler)
- **Tech Logger** → `logs/logs.log` (RotatingFileHandler, DEBUG)
- Configuración declarativa via YAML (`spec/user_logger.yaml`)
- Validación de spec al inicio (`SpecValidator`)
- Guard contra mutación del root logger (`root_logger_guard`)

```python
logger.error(
    f"Error técnico: {exception}",
    exc_info=True,
    user_msg="No se pudo procesar el archivo. Verifique el formato."
)
```

## Consecuencias

### Positivas
- Separación clara de audiencias
- Mensajes de usuario legibles sin ruido técnico
- Stack traces completos disponibles para debugging
- Configuración validada al inicio (fail-fast)
- Rotación automática de archivos de log

### Negativas
- Complejidad adicional en el sistema de logging
- Requiere pasar `user_msg` explícitamente en cada llamada
- La spec YAML añade un nivel de indirección
- El guard del root logger puede interferir con librerías de terceros
