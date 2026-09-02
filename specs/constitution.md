### Constitución - facture_new

**Versión:** 1.1.0 | **Ratificada:** 2026-09-02 | **Última enmienda:** 2026-09-02

#### Principios innegociables
Principios innegociables. Toda spec, plan y tarea debe cumplirlos.

- **Simplicidad:** Python 3.12+, alembic para migraciones, Polars para manejo de Excel (nunca pandas) y xlsxwriter para escritura.
- **Spec manda:** ningún comportamiento se implementa si no está en la spec activa. Si falta una decisión, se detiene el trabajo y se pregunta.
- **Lógica separada:** arquitectura hexagonal (domain → application → infrastructure), DRY y SOLID Principles. En concreto: los repositorios son interfaces ABC en `domain/repositories/`, implementadas en `infrastructure/persistence/` con prefijo `Sa*` y devuelven siempre `list[dict]` (nunca objetos ORM); los tests usan fakes manuales (`Fake*Repo`), nunca mocks/patches.
- **Test:** se debe trabajar sobre TDD (test driven development) en las implementaciones, separado por módulos en `tests/fakes/` si se requiere; no puede haber test en rojo si hay test en verde.
- **Idioma:** español para mensajes al usuario, inglés para código.
- **Verificar, nunca crear:** el sistema nunca crea registros (clientes, empresas) automáticamente en sistemas externos (Odoo); cuando no encuentra una coincidencia exacta, marca el registro para revisión manual en vez de insertar directamente.
- **Integraciones externas idempotentes y auditables:** toda escritura hacia un sistema externo (Odoo XML-RPC, RUES) debe deduplicarse/ser idempotente y dejar rastro en un log de auditoría antes de ejecutarse.

#### Enmiendas
Cambiar un principio innegociable requiere justificación explícita del usuario y actualización de versión (semver): PATCH para aclaraciones de redacción, MINOR para agregar principios, MAJOR para eliminar o redefinir uno existente. Toda enmienda registra aquí fecha y motivo.

**Historial:**
- 1.1.0 (2026-09-02): se agrega gobernanza (versión/fechas/enmiendas); se agregan los principios "Verificar, nunca crear" e "Integraciones externas idempotentes y auditables"; se especifica "Lógica separada" con las convenciones de repos ABC/`Sa*`/`list[dict]`/fakes; se prohíbe explícitamente pandas dentro de "Simplicidad".
- 1.0.0 (fecha no registrada): versión original con 5 principios base (Simplicidad, Spec manda, Lógica separada, Test, Idioma).
