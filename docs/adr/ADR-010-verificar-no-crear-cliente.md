# ADR-010: VERIFICAR en Lugar de Creación Automática de Clientes en Odoo

## Estado
Aceptado

## Fecha
2026-06-05

## Contexto

Cuando una empresa del consolidado no se encuentra en Odoo (ni por NIT ni por nombre), el sistema podría:
1. Crear automáticamente el cliente en Odoo con los datos disponibles
2. Marcar la empresa como pendiente de verificación manual
3. Abortar todo el proceso de inyección

El riesgo de crear clientes automáticamente es alto: datos incompletos (sin dirección, sin régimen fiscal, sin DV correcto) generarían registros inconsistentes en el ERP.

## Decisión

Cuando un cliente no se encuentra en Odoo, el sistema:
- Retorna status **"VERIFICAR"** con mensaje `"Empresa no encontrada en Avancys con NIT: {nit}"`
- NO crea el cliente automáticamente
- Registra el caso en el log de inyección para revisión manual
- El operador debe crear/corregir el cliente en Odoo y re-ejecutar

## Consecuencias

### Positivas
- Previene creación de registros de cliente incompletos o erróneos
- El ERP mantiene su integridad de datos
- El operador tiene visibilidad de qué empresas requieren atención
- Se puede re-ejecutar después de corregir sin riesgo (lógica anti-duplicados)

### Negativas
- Requiere intervención manual para empresas nuevas
- El proceso no es 100% automático en el primer run con empresas nuevas
