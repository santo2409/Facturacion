# Diseño de la integración ETL-Avancys → Facturacion

Fecha: 2026-11-23. Fuentes: `docs/etl-analisis.md` (contrato T1-T30 y §6 solapamiento), `docs/auditoria.md`
(comparación con el ETL y respuestas P-10, P-11, P-12, P-14, P-15, P-26) y `CLAUDE.md`.
Referencia de paridad: `ETL-Avancys/Pipeline.py` en el commit `7bb6784`, sin cambios.

**Objetivo.** La opción 5 del menú, "Cargar Pre Facturas" (antes opción 8), hace lo mismo que `Pipeline.py`:
lee las pre-facturas `.xlsx` de una carpeta y crea **una factura borrador por empresa** en Odoo, con
**paridad exacta** en lo que se envía a Odoo y en los libros de salida. Reemplaza el flujo viejo de
`src/odooInjection` (P-14).

### Decisiones ya tomadas

| ID | Decisión | Fuente |
|---|---|---|
| E-01 | La opción **pide la carpeta** de entrada, como `datos/Entrada/` en el ETL: lee los `.xlsx` del primer nivel | Usuario, 2026-11-23 |
| E-02 | Cliente solo por `ref_num` exacto (`nit`, `nit_limpio`); 0 o 2+ terceros → VERIFICAR; nunca por nombre ni `vat` | P-11 |
| E-03 | Anti-duplicados = la guarda en Odoo del ETL (borrador del mismo tercero, diario, usuario y día) + `YA_SUBIDAS`. **Sin** el log local de ADR-009 | P-10 |
| E-04 | `NITS_BLOQUEADOS`, `EMPRESAS_BLOQUEADAS` y `YA_SUBIDAS` viven en **un Excel de configuración** que el usuario edita y sube | Usuario, 2026-11-23; P-26 |
| E-05 | `ACTUALIZAR_PRECIOS` se conserva, **apagado** por defecto, con una variable de entorno | Usuario, 2026-11-23 |
| E-09 | Los comportamientos dudosos se **copian tal cual** para la paridad; cada corrección va después, en su propio commit aprobado | Usuario, 2026-11-23 |
| E-12 | Los scripts auxiliares del ETL (`revisar_odoo.py`, `codigos_repetidos.py`, `ExportarTarifa.py`, `Tarifas.py`) quedan fuera | Propuesta (sección 8) |
| E-13 | El flujo viejo de inyección se **retira** cuando la paridad esté en verde (último paso) | P-14 |
| P-12 | La factura va **sin fechas** y se limpia el vencimiento después de crearla | P-12 |
| P-13 | Las dos autorretenciones van en todas las líneas; se acepta el respaldo `ilike` del nombre del impuesto | P-13 |

---

## Ubicación del módulo

`src/odooInjection/`, el lugar natural según `CLAUDE.md`. El código nuevo convive con el viejo, con nombres
distintos, hasta el último paso, y después se borra lo viejo. No se crea otro módulo porque el adaptador de Odoo y
`get_odoo_config` ya viven aquí y los usan las opciones 1, 2 y 3.

```
src/odooInjection/
├── config.py                         # get_odoo_config (compartido) + get_injection_config (nuevo)
├── domain/
│   ├── entities/
│   │   ├── pre_invoice_row.py         # NUEVO  fila interna (COLS_FIJAS + exámenes)           T6
│   │   ├── company_batch.py           # NUEVO  filas agrupadas por NIT + nombre de la última fila T8
│   │   ├── injection_settings.py      # NUEVO  bloqueos + YA_SUBIDAS (Excel de configuración) E-04
│   │   ├── injection_outcome.py       # NUEVO  estado por empresa (OK/VERIFICAR/ERROR) + detalle
│   │   ├── pending_exam.py            # NUEVO  examen apartado (sin cuenta / sin producto)    T19, T23
│   │   └── analytic_account_maps.py   # NUEVO  CIUDAD_CUENTA, CIUDAD_CUENTA_ID, SEDE_CUENTA, RAMA_PRIORIDAD (copia del ETL)
│   ├── repositories/
│   │   ├── pre_invoice_source.py      # NUEVO puerto: lee archivos → filas, archivos ilegibles
│   │   ├── injection_settings_source.py  # NUEVO puerto: lee el Excel de configuración
│   │   ├── injection_gateway.py       # NUEVO puerto: operaciones de Odoo que usa la inyección
│   │   └── injection_report_writer.py # NUEVO puerto: libros, CSV y copias a verificar/
│   └── services/
│       ├── nit_rules.py               # NUEVO nit_valido, nit_limpio                           T15
│       ├── city_key.py                # NUEVO _normalizar/_clave_ciudad/_trozos                T20
│       ├── analytic_account_resolver.py  # NUEVO resolver_cuenta_analitica sobre un índice     T19-T21
│       ├── company_checks.py          # NUEVO cobro doble, período por Base, bloqueos          T7, T11-T14
│       └── invoice_builder.py         # NUEVO líneas, cuadre, cabecera                         T22-T27
├── application/use_cases/
│   └── load_pre_invoices_to_odoo.py   # NUEVO orquestador
└── infrastructure/
    ├── persistence/
    │   ├── xlsx_pre_invoice_source.py     # NUEVO lector de plantilla por nombre de columna    T1-T5
    │   └── xlsx_injection_settings_source.py  # NUEVO
    ├── odoo/
    │   ├── xmlrpc_odoo_repository.py      # EXISTENTE: se reutiliza sin cambiar su comportamiento
    │   └── xmlrpc_injection_gateway.py    # NUEVO adaptador del puerto (compone el existente)
    ├── reporting/
    │   └── etl_injection_report_writer.py # NUEVO los 4 libros + CSV + verificar/ del ETL
    └── console/
        └── load_pre_invoices_controller.py  # NUEVO raíz de composición de la opción 5
```

Pruebas: `tests/odooInjection/` refleja la estructura; los fakes de los cuatro puertos van en `tests/fakes/`;
la paridad en `tests/paridad/test_paridad.py`.

**Lo que se borra en el último paso (E-13)**: `inject_invoices_to_odoo.py`, `excel_pre_invoice_reader.py`,
`city_account_resolver.py`, `city_account_map.py`, `excel_log_generator.py`, `inject_invoices_controller.py`,
`invoice_line.py`, `invoice_result.py`, `pre_invoice_reader_repository.py`, sus pruebas, el escenario golden
`opcion8_inyeccion` y los métodos del adaptador que solo usaba ese flujo (`find_date_range`, `create_client`,
`find_analytic_account`), además de `fecha_servicio` y `fecha_vencimiento_dias` en `get_odoo_config`.

## Componentes

| Componente | Clase | Responsabilidad | Reglas del ETL |
|---|---|---|---|
| **Extractor** | `XlsxPreInvoiceSource` (puerto `PreInvoiceSource`) | Lista los `.xlsx` de la carpeta (primer nivel, sin `~$` ni `consolidado`, por nombre); lee la **primera hoja** como texto; fila 2 = encabezados, datos desde la 3; valida las 7 columnas obligatorias y avisa de las 6 opcionales; detecta exámenes por la regex `^\d{6}(-\d{1,2})?$` tras quitar el sufijo literal `.0`; arma `PreInvoiceRow`; separa los archivos ilegibles o con la plantilla cambiada | T1-T6, T10; P:873-976, 1682-1687, 1740-1743 |
| Extractor (config) | `XlsxInjectionSettingsSource` | Lee el Excel de configuración: NITs bloqueados, empresas bloqueadas (prefijo normalizado), ya subidas (NIT → factura) | E-04; P:147-175 |
| **Transformador** | Servicios de dominio puros, sin E/S | `company_checks`: período por `Base` (T7), cobro doble (T11), empresa bloqueada (T12), `YA_SUBIDAS` (T13), NIT bloqueado (T14). `nit_rules` (T15). `analytic_account_resolver`: sede → EXTRAMURAL → id → código confirmado por nombre → PROVEEDORES; ciudad exacta → palabra → WRatio ≥ 95 con ganador único; familia y rama; sin respaldo (T19-T21). `invoice_builder`: líneas por (código, cuenta) con `quantity` = pacientes, orden `sorted(key=str)`, cuenta 42650/42653, `tax_ids`, UdM, cuadre y cabecera sin fechas con `narration` sin tilde (T22-T27) | T7, T11-T15, T19-T27 |
| **Cargador** | `XmlRpcInjectionGateway` (puerto `InjectionGateway`) | Conectar (3 intentos, 5 s); cliente por `ref_num` (`limit 2`); producto por `default_code`; índice completo de cuentas analíticas y búsqueda por `code`; impuesto y UdM; guarda anti-duplicados (`search_read` de borradores del día); `create` de `account.move`; `write invoice_date_due=False`; `update_puchase_line_prices` por JSON-RPC solo si está encendido | T16-T18, T28-T29; P:536-613, 624-646, 791-864, 1252-1278 |
| **Orquestador** | `LoadPreInvoicesToOdoo` | Lee la config y los archivos, agrupa por NIT (T8-T9), y por empresa: chequeos → cliente → impuestos/UdM → cuentas por paciente → productos → líneas → cuadre → guarda → crear → limpiar vencimiento → registrar. Reintenta la empresa completa ante `OSError`/`ProtocolError` (3 veces, 10 s, reconexión); cualquier otra excepción → ERROR (150 caracteres) y sigue. Guarda los libros cada 10 empresas y al final. Al terminar muestra **un** resumen (ADR-014) | T8-T10, T25-T26; P:1798-1862 |
| Reportes | `EtlInjectionReportWriter` (puerto `InjectionReportWriter`) | `log_inyeccion.xlsx` (10 columnas + Total, Precios, colores e hipervínculos), `pendientes_facturador.xlsx` ("Subir a mano", "Empresas sin factura"), `cuentas_por_revisar.xlsx` ("Arreglar en Odoo"), `facturas_creadas.csv` (`factura_id;nit;empresa;url`, escrito factura a factura) y copias a `verificar/`. Mismos nombres, hojas, columnas y formato que el ETL | P:1403-1667, 1791-1792, 1837-1841 |
| Controller | `load_pre_invoices_controller.load_pre_invoices(logger)` | Valida la config de Odoo, lee (o crea) el Excel de configuración, pide la carpeta de entrada, arma la carpeta de salida, instancia los adaptadores y ejecuta el caso de uso. **No** llama a `get_session()` (el flujo no usa BD) | E-01; ADR-001 |

## Reutilización

**Se reutiliza tal cual (sin cambiar comportamiento; el golden sigue en verde):**

| Qué | Dónde | Para qué |
|---|---|---|
| `XmlRpcOdooRepository.connect`, `_execute`, transportes con timeout | `src/odooInjection/infrastructure/odoo/xmlrpc_odoo_repository.py` | El gateway nuevo **compone** este adaptador para conectar y ejecutar `execute_kw`; no se duplica la conexión |
| `find_product`, `find_tax`, `find_uom` | mismo archivo | Equivalentes verificados al ETL (§6.3) |
| `get_odoo_config` (URL, DB, usuario, API key, diario, cuentas, impuestos, UdM, productos gravados) | `src/odooInjection/config.py` | Mismos valores por defecto que el ETL. Se usa `ODOO_USERNAME`; `ODOO_USER` del ETL se descarta |
| `load_env` | `src/shared/env.py` | Carga del `.env` (el `.env` gana; el parser propio del ETL se descarta) |
| `LoggerAdapter` (`user_msg`), `USER_CONSOLE`, `RichProgress`, `safe_dispatch` | `src/shared/logging`, `src/shared/console`, `main.py` | Log técnico en `logs.log`, resumen único en consola, barra de progreso por empresa |
| `ask_excel_path`, entrada de carpeta | `src/shared/console/file_input.py` | Pedir el Excel de configuración y la carpeta (se agrega una función para pedir carpeta si no existe; `file_output.ask_directory_path` se eliminó el 2026-11-23) |
| `OdooSimulado` | `tests/golden/_odoo_simulado.py`, `tests/paridad/capturar_referencia.py` (`OdooParidad`) | Pruebas de carga y paridad |

**Es nuevo** (no existe en Facturacion o existe con otro comportamiento, §6 de `etl-analisis.md`): lector por
nombre de columna, reglas de NIT del ETL, normalización de ciudad, resolución de cuentas con mapas nuevos, búsqueda
de cliente por `ref_num` exacto, chequeos de bloqueo y calidad, armado de líneas y cabecera, guarda anti-duplicados,
limpieza del vencimiento, JSON-RPC de precios, reintento por empresa y los cuatro libros del ETL.

**Qué no se duplica:** no se copia la conexión XML-RPC, ni `find_product/tax/uom`, ni la carga del `.env`, ni el
logging, ni el progreso. Lo que parece duplicado no lo es:

| Parece igual | Por qué es nuevo |
|---|---|
| `nit_valido` vs `normalize_nit` | `normalize_nit` corta a 9 dígitos y no valida longitud; el ETL acepta 6-12 dígitos y busca `nit` y `nit_limpio` tal cual (§6.4, riesgo alto) |
| `analytic_account_resolver` vs `CityAccountResolver` | Otro mapa, otro umbral (95 vs 80), sedes, ids y sin respaldo a Bogotá (§6.3, riesgo alto). El viejo se borra en el último paso |
| Cliente por `ref_num` vs `find_client` | `find_client` busca por `vat` y `=like`, se queda con el menor id y lo usan las opciones 1, 2 y 3: no se toca. El método nuevo vive en el gateway de la inyección |
| `EtlInjectionReportWriter` vs `FindingsWriter` | Los libros del ETL tienen hojas, colores, hipervínculos y totales propios que la operación ya consume; `FindingsWriter` hace un libro plano por tipo |

## Configuración

Las variables existentes de Odoo no cambian. Nuevas, todas en `get_injection_config()` (en `src/odooInjection/config.py`),
con el patrón de `src/shared/config.py`: sin valor seguro → `""` y el controller decide abortar.

| Variable | Por defecto | Uso | Equivale en el ETL |
|---|---|---|---|
| `ODOO_ACTUALIZAR_PRECIOS` | `false` | Llama a `update_puchase_line_prices` tras crear cada factura (E-05) | `ACTUALIZAR_PRECIOS` (P:138) |
| `INYECCION_CONFIG_XLSX` | `configuracion_inyeccion.xlsx` | Ruta del Excel de configuración (E-04). Si no existe, el controller lo crea con los valores del ETL y se detiene para que se revise | `NITS_BLOQUEADOS`, `EMPRESAS_BLOQUEADAS`, `YA_SUBIDAS` (P:147-175) |
| `INYECCION_SALIDA` | `logs/cargar_prefacturas` | Carpeta base de las salidas; cada corrida crea `<base>/<AAAA-MM-DD_HHMM>/` (ADR-014) | `datos/Salida/` (P:88-99) |

**Excel de configuración** (`configuracion_inyeccion.xlsx`, lo edita el usuario):

| Hoja | Columnas | Regla |
|---|---|---|
| `NITS_BLOQUEADOS` | `NIT`, `MOTIVO` | NIT limpio → VERIFICAR sin tocar Odoo (T14) |
| `EMPRESAS_BLOQUEADAS` | `NOMBRE`, `MOTIVO` | Prefijo del nombre normalizado sin tildes → VERIFICAR (T12) |
| `YA_SUBIDAS` | `NIT`, `FACTURA` | NIT limpio → OK con la factura indicada, sin crear (T13) |

Si falta el archivo, se crea con los valores que tenía `Pipeline.py` (`valores_del_etl()`) y la corrida se detiene.
Si falta una hoja o una columna, se detiene con un mensaje que nombra el archivo y la hoja. Una hoja **vacía** es válida.

**Constantes que no son configuración**: los mapas de cuentas (`CIUDAD_CUENTA` ~120 ciudades, `CIUDAD_CUENTA_ID`,
`SEDE_CUENTA`, `RAMA_PRIORIDAD`, `UMBRAL_CIUDAD=95`) se copian **en código** en `analytic_account_maps.py` para la
paridad. Dónde viven a largo plazo (P-15: "código, BD y Odoo") está en D-1.

## Punto de entrada y programación

- **CLI**: opción 5 del menú, "Cargar Pre Facturas". `dispatch_option("5")` llama a `load_pre_invoices(logger)`.
  Mientras dura la integración, la opción 5 sigue desconectada y el controller nuevo se prueba de forma directa;
  se conecta en el paso *orquestación*.
- **Programación**: ninguna. El proceso es **mensual y manual**, como hoy con el ETL (README del ETL, "El proceso de
  cada mes"). No hay tarea programada ni endpoint.
- **Flujo mensual**: opción 3 (Asignar Tarifas) → opción 4 (Generar Pre Facturas) → el usuario revisa y copia las
  pre-facturas a una carpeta → opción 5 con esa carpeta y el Excel de configuración → revisar
  `logs/cargar_prefacturas/<fecha>/`.
- **Convivencia con el ETL**: hasta el cierre, no correr el ETL y la opción 5 sobre el mismo lote. La guarda
  anti-duplicados protege el mismo día (las dos usan el mismo usuario de Odoo); entre días, solo `YA_SUBIDAS`.

## Estrategia de pruebas

1. **Unitarias por regla** (pytest con fakes manuales, ADR-005): al menos una prueba por cada T1-T30 que aplique,
   nombrada con la regla, por ejemplo `test_t19_sede_103_en_otra_ciudad_queda_apartada`. Los servicios de dominio
   son puros y se prueban sin Odoo. Los casos salen de §2 de `etl-analisis.md` y de los 9 casos dirigidos de
   `tests/paridad/entradas/`.
2. **Adaptador**: `XmlRpcInjectionGateway` contra `OdooSimulado` (sin red), incluidos reintentos de conexión y la
   guarda del mismo día con `create_date` en UTC (E-10).
3. **Paridad** (`tests/paridad/test_paridad.py`): ejecuta el caso de uso real sobre `tests/paridad/entradas/`
   (las pre-facturas se generan con `construir_entradas.py` si faltan, porque `*.xlsx` está en `.gitignore`)
   contra `OdooParidad`, con la misma URL ficticia, aplica `normalizar.py` y compara con `tests/paridad/esperado/`:
   - `odoo_escrituras.json`: **igual exacto**: cada `create` (cabecera y líneas en orden) y cada `write`;
   - `log_inyeccion.xlsx.json`, `pendientes_facturador.xlsx.json`, `cuentas_por_revisar.xlsx.json`,
     `facturas_creadas.csv`, `verificar.json`: **igual exacto**;
   - `log_inyeccion.txt`: **no se compara** (el logging se reemplaza por `logs.log`, §6.8). Si un aviso de
     negocio del `.txt` no aparece en ningún libro, se deja en el log técnico y se lista como diferencia aceptada.
4. **Golden y suite**: el golden y la suite siguen en verde en cada commit (regla 4). El escenario
   `opcion8_inyeccion` se retira solo en el último paso.

**Requisito previo**: `tests/paridad/esperado/` todavía no existe. La captura del 2026-11-09 (`/tmp/etl_run1`)
se repitió el 2026-11-23 (`/tmp/etl_run3`) y es idéntica. Hay que copiarla. Lo hace el usuario, porque la escritura
en `esperado/` está bloqueada para el agente:
`cp -r /tmp/etl_run1 tests/paridad/esperado`.

## Estado (2026-11-23)

Implementados los pasos esqueleto → paridad en un solo commit a pedido del usuario ("que funcione tal cual como el ETL").
Nombres finales: `etl_constants.py` reúne los mapas y las constantes de plantilla (en vez de `analytic_account_maps.py`
y `pre_invoice_row.py`); las filas se manejan como `dict` y tuplas, igual que en el ETL. Verificación:
- `tests/paridad/test_paridad.py`: escrituras a Odoo, libros y CSV idénticos a la captura del ETL.
- Lector sin pandas idéntico a `pd.read_excel` en las 315 pre-facturas reales (`verificar_lector.py`).
- 315 pre-facturas reales con un Odoo sintético: 548 escrituras idénticas entre ETL e integración.
Pendiente: paso *retiro* del flujo viejo (requiere borrar el escenario golden `opcion8_inyeccion` y la clave
`cuenta_analitica` del esperado de `normalizadores`, que usa `CityAccountResolver`).

## Plan de pasos
| Paso | Entregable | Terminado cuando |
|------|------------|------------------|
| 0. referencia | `tests/paridad/esperado/` con la captura del ETL `7bb6784` | La carpeta existe, versionada; `diff -r` contra una captura nueva sale vacío |
| esqueleto | Entidades, los 4 puertos, sus fakes en `tests/fakes/`, `get_injection_config`, controller vacío; `test_paridad.py` creado y marcado `xfail` | Todo importa; pruebas de config y de los fakes en verde; golden 8/8 y suite en verde; el menú sin cambios |
| extraccion | `XlsxPreInvoiceSource` y `XlsxInjectionSettingsSource` | Pruebas T1-T6, T10 y del Excel de configuración en verde. Sobre `tests/paridad/entradas/`: mismos archivos aceptados, el mismo ilegible (`901000005`), mismas columnas de examen y mismos valores de texto que el ETL (comparados contra `pd.read_excel(dtype=str)` en una prueba que corre con el venv del ETL o con valores fijados) |
| transformacion | `nit_rules`, `city_key`, `analytic_account_resolver`, `company_checks`, `invoice_builder`, `analytic_account_maps` | Una prueba por regla T7-T27 en verde; para los casos dirigidos (sedes, EXTRAMURAL, MARIQUITA, ciudad fuera del mapa, código repetido, BUGA, gravado 100006, inexistente 999999, cobro doble, dos meses) el resultado coincide con lo que registra `esperado/` |
| carga | `XmlRpcInjectionGateway` | Pruebas contra `OdooSimulado`: `ref_num` con 0/1/2 terceros, índice de cuentas, guarda del mismo día (UTC), `create` + `write`, JSON-RPC apagado y encendido, 3 intentos de conexión. `find_client` y el adaptador existente sin cambios (pruebas de las opciones 1-3 en verde) |
| orquestacion | `LoadPreInvoicesToOdoo`, `EtlInjectionReportWriter`, controller conectado a la opción 5 | Reintento por empresa, guardado cada 10, resumen único en consola, libros en `logs/cargar_prefacturas/<fecha>/`; prueba del menú actualizada; golden y suite en verde |
| paridad | `test_paridad.py` sin `xfail` | `odoo_escrituras.json` y los libros iguales a `esperado/`; dos corridas seguidas iguales; diferencias aceptadas (solo `.txt`) documentadas en `tests/paridad/LEEME.md` |
| retiro | Borrado del flujo viejo (E-13) | Archivos listados en *Ubicación* eliminados; escenario golden `opcion8_inyeccion` retirado (el usuario borra su esperado); guardián de código muerto ampliado; docs de usuario actualizadas; suite y golden en verde |

Cada paso = un commit `feat(odooInjection): <paso> — …` (regla 5), con golden y suite en verde antes (regla 4).

## Riesgos y decisiones

### Decisiones (aceptadas por el usuario el 2026-11-23: todas las recomendaciones)

| ID | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D-1 | Dónde viven los mapas de cuentas (P-15 dice "en los 3": código, BD y Odoo) | (a) En código, copia del ETL; (b) tabla en BD que se carga desde un Excel; (c) leer el mapa desde Odoo | (a) para la paridad. Después, (b) como cambio aparte si el mapa cambia seguido. Odoo ya se consulta para validar que la cuenta exista y sea de la ciudad |
| D-2 | Valor del examen en los libros: el ETL usa `float` (`"$12,500"` → `12500.0`) y `format(",.0f")`. `CLAUDE.md` prohíbe `float` en montos | (a) `float` solo dentro de los libros de pendientes y cuentas, como excepción documentada; (b) `Decimal` | (a): el valor no llega a Odoo y así la paridad es exacta. (b) puede cambiar el redondeo de sumas largas |
| D-3 | Lectura de la plantilla: el ETL usa `pd.read_excel(dtype=str)` y Facturacion no tiene pandas | (a) openpyxl con la misma conversión a texto que pandas; (b) Polars/fastexcel con `infer_schema_length=0`; (c) agregar pandas | (a), con pruebas que fijen la conversión de enteros, decimales, fechas y vacíos. (b) da otros textos para los números (`"150000"` frente a `"150000.0"`). (c) suma una dependencia pesada |
| D-4 | Carpeta y nombres de salida | (a) `logs/cargar_prefacturas/<fecha>/` con los nombres del ETL; (b) una carpeta fija como `datos/Salida/` | (a): ADR-014 y una carpeta por corrida. Así `facturas_creadas.csv` ya no se pierde al iniciar otra corrida, aunque se copia la escritura del ETL (E-09) |
| D-5 | Timeout de 180 s del adaptador (E-11); el ETL no tiene | Aceptar / quitarlo para la inyección | Aceptar: en el simulador no cambia nada y la guarda protege el reintento |
| D-6 | La guarda compara la medianoche local con `create_date` en UTC (E-10) | Copiar / corregir | Copiar (E-09) y corregir después si se decide |
| D-7 | Fuente de verdad del ETL (E-06): ETL-Avancys `7bb6784` o Facturas-Avancys | — | `7bb6784`. Si cambia `Pipeline.py` en producción durante la integración, se vuelve a capturar `esperado/` y se revisan las diferencias |
| D-8 | Validar el simulador contra la instancia de pruebas de Odoo (E-07) | Sí (requiere autorización y limpiar los borradores) / No | Opcional, una vez antes del paso *retiro* |

### Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Diferencias de texto al leer Excel sin pandas (D-3) | Alto: NIT o códigos distintos cambian clientes y productos | Prueba de extracción comparada con lo que lee pandas; paridad exacta de `odoo_escrituras.json` |
| El ETL cambia en producción durante la integración | Medio: la referencia queda vieja | Fijar el commit; volver a capturar y comparar antes de *paridad* y de *retiro* |
| Correr el ETL y la opción 5 sobre el mismo lote en días distintos | Alto: facturas duplicadas en Odoo | `YA_SUBIDAS` en el Excel de configuración; regla operativa: un solo inyector por lote |
| La referencia solo cubre los casos de `tests/paridad/entradas/` (sin fallos de red ni el Odoo real) | Medio | Pruebas unitarias de reintento y guarda; validación opcional D-8 |
| Comportamientos dudosos copiados (E-09) | Bajo/Medio: doble conteo tras un reintento, `narration` con filas | Lista en `etl-analisis.md` E-09; un commit aprobado por cada corrección después de la paridad |
| Retirar el flujo viejo rompe a quien comparte el adaptador | Medio | Solo se borran métodos que nadie más usa (comprobado con el mapa de importaciones); pruebas de las opciones 1-3 en verde |
| El escenario golden `opcion8_inyeccion` y `tests/paridad/esperado/` están protegidos contra escritura del agente | Bajo | El usuario copia y borra esos archivos cuando el plan lo indique |
