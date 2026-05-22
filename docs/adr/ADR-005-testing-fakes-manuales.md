# ADR-005: Testing con Fakes Manuales en lugar de Mocks

## Estado
Aceptado

## Fecha
2024-12-14

## Contexto

El sistema necesita tests unitarios para los casos de uso que dependen de múltiples repositorios (BD), servicios externos (RUES) y utilidades (fuzzy matching, progreso). Se requiere:
- Tests rápidos sin conexión a BD ni internet
- Verificación del comportamiento de negocio aislado
- Mantenibilidad a largo plazo

Alternativas evaluadas:
1. `unittest.mock` / `pytest-mock` — Mocks dinámicos
2. Fakes manuales — Implementaciones in-memory de interfaces
3. Test containers — BD real en Docker

## Decisión

Se implementan **Fakes manuales** para cada repositorio e interfaz:

```python
class FakeBillerRepo:
    def __init__(self):
        self._billers = []

    def find_by_name(self, name):
        return next((b for b in self._billers if b["name"] == name), None)

    def save(self, biller):
        self._billers.append(biller)
    ...
```

Cada fake:
- Implementa la misma interfaz que el repositorio real
- Almacena datos en listas/diccionarios en memoria
- Permite pre-cargar estado para escenarios de test

## Consecuencias

### Positivas
- Tests extremadamente rápidos (sin I/O)
- Comportamiento predecible y determinista
- Los fakes sirven como documentación de la interfaz esperada
- Errores de contrato se detectan al compilar/ejecutar (no en runtime con mocks)
- No hay acoplamiento a la implementación interna (no se verifica "fue llamado con X")

### Negativas
- Requiere mantener los fakes sincronizados con las interfaces reales
- Más código boilerplate que usar `mock.patch`
- No detecta cambios en la firma de métodos automáticamente

## Notas
Los fakes se centralizan en `tests/fakes/` y se inyectan via fixtures de pytest en `conftest.py`, facilitando su reutilización entre módulos de test.
