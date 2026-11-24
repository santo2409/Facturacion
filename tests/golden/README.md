# Golden master (pruebas de caracterización)

Fija el comportamiento **actual** de Facturacion, incluidos sus bugs, antes de optimizar.
Si una prueba falla, el sistema cambió de comportamiento: se corrige el código o se
consulta. **Nunca se regenera un esperado para que la prueba pase** (CLAUDE.md, regla 3).

```bash
pytest tests/golden -v                       # correr
python tests/golden/generar_esperado.py      # crear esperados que falten (no sobrescribe)
python tests/golden/generar_esperado.py --forzar opcion6_asignar   # sobrescribir uno (solo con un cambio aprobado)
python tests/golden/construir_entradas.py --forzar                 # reconstruir entradas (cambia la base)
```

## Cómo funciona

`_arnes.py` ejecuta los **controllers reales** de cada opción del menú dentro de un
directorio temporal y toma una instantánea JSON de todo lo que producen: archivos
creados o modificados, estado final de la BD simulada, escrituras en Odoo, texto de
consola y mensajes al usuario (`user_msg`). `test_golden_master.py` la compara con
`esperado/<escenario>.json` y, si difieren, muestra el diff.

| Es real (se ejecuta tal cual) | Se sustituye (frontera externa) |
|---|---|
| Controllers, casos de uso, servicios de dominio | Preguntas al usuario (`ask_excel_path`, `ask_sheet_name`, `ask_directory_path`) |
| Lectura de Excel (calamine/openpyxl) y escritura (xlsxwriter/openpyxl) | PostgreSQL: `get_session` y `Sa*Repository` → repos en memoria desde `bd.json` |
| Generadores de libros y hallazgos | Odoo: `xmlrpc.client.ServerProxy` → `_odoo_simulado.py` (desde `odoo.json`) |
| `XmlRpcOdooRepository` (adaptador Odoo) | RUES: `RuesPlaywrightScraper` → `FakeNitScraper` (desde `rues.json`) |
| `SaCompanyNitCacheRepository`, `RapidFuzzBiller`, normalizadores | Reloj (fecha y hora fijas) |

No se modifica código de producción: todo se hace con `monkeypatch` sobre nombres
importados en los controllers.

## Escenarios y cobertura de docs/auditoria.md

| Escenario | Qué ejecuta | Casos fijados |
|---|---|---|
| `normalizadores` | Funciones puras | `normalize_nit` (AUD-28, P-09), `fuzz_property` (AUD-03) |
| `opcion1_web_scrapping` | `execute_web_scrapping` | Cascada Odoo → BD → RUES, nombre corto ⊂ partner de Odoo cambia el NIT (AUD-03), RUES sin respuesta = "No encontrado" (AUD-06), NIT solo en BD fuera del libro (AUD-14), NIT vacío como "None" (AUD-72), cédula de 10 dígitos |
| `opcion2_facturadores` | `import_billers` | Gestor por fuzzy, cédula truncada (AUD-26), empresa no verificada guardada (AUD-27), vínculo duplicado: gana la última fila |
| `opcion6_asignar` | `assign_rates(with_invoices=True)` | Odoo especial/base, truncamiento `int()`, precio 0 ignorado, tarifa vencida; fases 1 a 6 y sin resolver; AUD-05 (dos candidatos en fase 3), AUD-18 (ciudad inexistente), fechas (AUD-48), Total con 1 y 2 (AUD-49, P-18), i-medical, TIAN, empresa por nombre en Odoo, NOVEDAD, FACTURAS |
| `opcion7_prefacturas` | `generate_pre_invoices` | Carpetas por facturador, SET / sin factura / SIN_FACTURADOR, NIT partido en dos carpetas (P-22), fila sin NIT, nombres de hoja de 31 caracteres (AUD-76), caracteres inválidos, Leyenda con "Fase 7" (AUD-56) |
| `menu_ventana_dias` | `main.dispatch_option` / `safe_dispatch` | Ventana DAY_INITIAL–DAY_FINAL y sus bordes (AUD-50), variable vacía o ausente (AUD-30) |

**No cubierto:** opciones 5 y 9 (en desuso) y 10; el scraper Playwright por dentro
(AUD-12); fallos de red y timeouts de Odoo (AUD-11, AUD-13); hallazgos sin efecto en
las salidas (rendimiento, sesiones, dependencias).

**Límite de AUD-05:** el repositorio en memoria devuelve la primera tarifa en orden de
inserción de `bd.json`, de forma estable. PostgreSQL sin `ORDER BY` no garantiza
ningún orden, así que el golden fija un caso posible, no el de producción. Cuando se
corrija AUD-05 con un criterio explícito, el esperado de `opcion6_asignar` cambiará
a propósito.

## Normalizaciones (solo lo que varía por naturaleza)

| # | Qué | Dónde | Por qué |
|---|---|---|---|
| N1 | **Reloj fijo**: 2026-11-05 10:30:00 (fin del mes anterior = 2026-10-31) | `fijar_reloj`; `clock=`/`today=` en writers, reporter y `AssignRatesFromExcel`; `monkeypatch` de `datetime`/`date` en `inject_invoices_to_odoo`, `odooInjection/config`, `not_found_companies_log_generator` y `main`; `assigned_rates._normalize_fecha` importa `date` dentro de la función, así que solo durante esa llamada se expone un módulo `datetime` con `today()` fijo | Fecha de ejecución: carpetas `logs/<opcion>/<AAAA-MM-DD_HHMM>/`, columnas "Fecha/Hora", fechas de la factura, tarifas vencidas y la lógica de fechas dependen del día |
| N2 | Ruta absoluta del directorio temporal → `<TMP>` | `normalizar` | Cada corrida usa un directorio distinto |
| N3 | Excel → JSON canónico: hojas en orden, valores, relleno, formato numérico, negrita, paneles inmovilizados, celdas combinadas. **No** se comparan los metadatos del archivo, anchos, bordes ni estilos de tabla | `leer_xlsx` | El `.xlsx` es un zip con fechas de creación; los bytes cambian en cada corrida aunque el contenido sea igual |
| N4 | Ids sustitutos de la BD → nombres (vínculos de la opción 2) | `esc_opcion2` | Los ids autoincrementales dependen del orden de inserción; en PostgreSQL pasa lo mismo |
| N5 | Entorno controlado: se borran las variables `ODOO_*`, `DIRECTORY`, `TIAN_NIT`, `BOOK_*`, `DAY_*`, etc., y se fijan por escenario. Nunca se leen sus valores reales | `entorno_controlado` | El `.env` local no debe cambiar el resultado. La configuración contable de Odoo usa los valores por defecto del código |
| N6 | Orden **no determinista del sistema actual** (verificado con distintos `PYTHONHASHSEED`): la lista de la columna FACTURAS (Asignar Tarifas). Se ordenan antes de comparar | `_orden_no_determinista` | El código agrupa sin `maintain_order` (AUD-80, AUD-81). No es una regla de negocio que el golden deba fijar; si se corrige, esta normalización se puede quitar |

Tampoco se comparan los mensajes técnicos (`logs.log`): solo los `user_msg`, que son
el contrato visible (ADR-014). Así, optimizar consultas o agregar logs técnicos no
rompe el golden.

## Determinismo

Verificado el 2026-11-05: la suite pasa dos veces seguidas y con `PYTHONHASHSEED`
= 1-6, 11, 22, 33 y 44. Una corrección simulada de AUD-01 hacía fallar el escenario de la antigua opción 3, así que el golden detecta cambios.

## Opciones eliminadas (2026-11-23)

Las opciones en desuso (Tratamiento Información, Cargar Tarifas, Registrar Empresas - Paquetes y
Generar Faltantes) se eliminaron del código y el menú se renumeró. Se retiraron sus escenarios
(`opcion3_tratamiento`, `opcion4_tarifas`) y, del escenario `normalizadores`, las claves
`normalize_document` y `valor_opcion3` (funciones eliminadas; el resto del esperado no cambió).
Los nombres de los escenarios que quedan (`opcion6_asignar`, `opcion7_prefacturas`) conservan la numeración
antigua: ahora son las opciones 3 y 4 del menú.

## Flujo viejo de inyección retirado (2026-11-24)

La opción 5 ahora es la integración de ETL-Avancys, cubierta por `tests/paridad/test_paridad.py`. Se retiraron
el escenario `opcion8_inyeccion` (congelaba el flujo viejo) y, del escenario `normalizadores`, la clave
`cuenta_analitica` (`CityAccountResolver`, eliminado); el resto del esperado no cambió.
