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
| `normalizadores` | Funciones puras | `normalize_nit` (AUD-28, P-09), `normalize_document`, VALOR opción 3 (AUD-01), `fuzz_property` (AUD-03), ciudad → cuenta analítica (AUD-08, AUD-09) |
| `opcion1_web_scrapping` | `execute_web_scrapping` | Cascada Odoo → BD → RUES, nombre corto ⊂ partner de Odoo cambia el NIT (AUD-03), RUES sin respuesta = "No encontrado" (AUD-06), NIT solo en BD fuera del libro (AUD-14), NIT vacío como "None" (AUD-72), cédula de 10 dígitos |
| `opcion2_facturadores` | `import_billers` | Gestor por fuzzy, cédula truncada (AUD-26), empresa no verificada guardada (AUD-27), vínculo duplicado: gana la última fila |
| `opcion3_tratamiento` | `import_information` | VALOR con miles y decimales (AUD-01), `str.replace` de una sola coincidencia (AUD-16), contratos fusionados por slug (AUD-17), CUP F0/F1/F2/F3 e inexistente |
| `opcion4_tarifas` | `import_rates` (2 corridas) | VALOR decimal ×10 (AUD-02), especial renombrado (AUD-04), contrato fuzzy → `contrato_no_existe` (AUD-15), CUP nulo aborta el resto (AUD-38), la última fila gana, PAQUETES→PAQUETE, alias de ciudad; 2ª corrida: CIUDAD vacía → excepción (AUD-82) |
| `opcion6_asignar` | `assign_rates(with_invoices=True)` | Odoo especial/base, truncamiento `int()`, precio 0 ignorado, tarifa vencida; fases 1 a 6 y sin resolver; AUD-05 (dos candidatos en fase 3), AUD-18 (ciudad inexistente), fechas (AUD-48), Total con 1 y 2 (AUD-49, P-18), i-medical, TIAN, empresa por nombre en Odoo, NOVEDAD, FACTURAS |
| `opcion7_prefacturas` | `generate_pre_invoices` | Carpetas por facturador, SET / sin factura / SIN_FACTURADOR, NIT partido en dos carpetas (P-22), fila sin NIT, nombres de hoja de 31 caracteres (AUD-76), caracteres inválidos, Leyenda con "Fase 7" (AUD-56) |
| `opcion8_inyeccion` | `inject_invoices` (2 corridas) | Anti-duplicados histórico (AUD-07), respaldo Bogotá (AUD-08), códigos analíticos repetidos (AUD-09), cliente por nombre equivocado (AUD-10), `rstrip(".0")` (AUD-19), columnas por posición (AUD-20), NIT con DV (AUD-21), partner duplicado → menor id (AUD-22), `range_id` de respaldo (AUD-23), impuesto por `ilike` (AUD-24), producto gravado con espacio (AUD-63), se excluye `*consolidado*` |
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
| N1 | **Reloj fijo**: 2026-11-05 10:30:00 (fin del mes anterior = 2026-10-31) | `fijar_reloj`; `clock=`/`today=` en writers, reporter y `AssignRatesFromExcel`; `monkeypatch` de `datetime`/`date` en `inject_invoices_to_odoo`, `odooInjection/config`, `not_found_companies_log_generator`, `cup_novelties_log_generator` y `main`; `assigned_rates._normalize_fecha` importa `date` dentro de la función, así que solo durante esa llamada se expone un módulo `datetime` con `today()` fijo | Fecha de ejecución: carpetas `logs/<opcion>/<AAAA-MM-DD_HHMM>/`, columnas "Fecha/Hora", fechas de la factura, tarifas vencidas y la lógica de fechas dependen del día |
| N2 | Ruta absoluta del directorio temporal → `<TMP>` | `normalizar` | Cada corrida usa un directorio distinto |
| N3 | Excel → JSON canónico: hojas en orden, valores, relleno, formato numérico, negrita, paneles inmovilizados, celdas combinadas. **No** se comparan los metadatos del archivo, anchos, bordes ni estilos de tabla | `leer_xlsx` | El `.xlsx` es un zip con fechas de creación; los bytes cambian en cada corrida aunque el contenido sea igual |
| N4 | Ids sustitutos de la BD → nombres (estado de catálogos, tarifas y vínculos en las opciones 2 y 4) | `_estado_tarifas`, `esc_opcion2` | `import_rates_from_excel._resolve_names` arma un `set`: el orden de inserción, y por tanto los ids autoincrementales, depende de `PYTHONHASHSEED`. En PostgreSQL pasa lo mismo |
| N5 | Entorno controlado: se borran las variables `ODOO_*`, `DIRECTORY`, `TIAN_NIT`, `BOOK_*`, `DAY_*`, etc., y se fijan por escenario. Nunca se leen sus valores reales | `entorno_controlado` | El `.env` local no debe cambiar el resultado. La configuración contable de Odoo usa los valores por defecto del código, salvo `ODOO_PRODUCTOS_GRAVADOS="890202, 903810-01"` en la opción 8 (AUD-63) |
| N6 | Orden **no determinista del sistema actual** (verificado con distintos `PYTHONHASHSEED`): filas de `logs/novedades_cups.xlsx` y su columna "Contratos (ejemplos)" (opción 3), y la lista de la columna FACTURAS (opción 6). Se ordenan antes de comparar | `_orden_no_determinista` | El código agrupa sin `maintain_order` (AUD-80, AUD-81). No es una regla de negocio que el golden deba fijar; si se corrige, esta normalización se puede quitar |

Tampoco se comparan los mensajes técnicos (`logs.log`): solo los `user_msg`, que son
el contrato visible (ADR-014). Así, optimizar consultas o agregar logs técnicos no
rompe el golden.

## Determinismo

Verificado el 2026-11-05: la suite pasa dos veces seguidas y con `PYTHONHASHSEED`
= 1-6, 11, 22, 33 y 44. Una corrección simulada de AUD-01 hace fallar `opcion3_tratamiento`, así que el golden detecta cambios.
