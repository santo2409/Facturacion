# Paridad con ETL-Avancys: salidas de referencia

Salidas de `ETL-Avancys/Pipeline.py` (commit `7bb6784`, **sin cambios**) contra un Odoo
**simulado**, para comparar después el módulo integrado en `src/odooInjection/`.
Procedimiento: `docs/etl-analisis.md` §8.

## Destino: solo el Odoo simulado

`capturar_referencia.py` nunca contacta un Odoo real:
- fija `ODOO_URL=http://odoo.simulado.invalid`, `ODOO_DB`, `ODOO_USER`, `ODOO_API_KEY` con valores ficticios
  (el ETL da prioridad al entorno sobre el `.env`: `Pipeline.py:69`) y aborta si encuentra un `.env`
  en las carpetas padre de la copia;
- sustituye `xmlrpc.client.ServerProxy` por `OdooParidad` (el `OdooSimulado` del golden + `write`, y las
  facturas creadas quedan visibles para la guarda anti-duplicados) antes de ejecutar el script;
- bloquea cualquier conexión de red (`socket.connect`, `socket.create_connection`);
- ejecuta una **copia** de `Pipeline.py` en `/tmp/etl_paridad_trabajo/` (ruta fija, porque aparece en el log),
  así que no se escribe nada en ETL-Avancys.

"Reiniciar el destino" = cada corrida es un proceso nuevo con un simulador cargado de `entradas/odoo.json`
(sin `account.move`), y los ids de factura empiezan siempre en 9001.

## Entradas congeladas (`entradas/`)

Opción elegida: **copia congelada de archivos**, no un rango de fechas. El ETL no extrae de una fuente
consultable por fechas: lee los `.xlsx` que haya en `datos/Entrada/` y consulta Odoo. Lo que se congela es:

- `prefacturas/`: 19 pre-facturas, todas ficticias (las 315 reales de `ETL-Avancys/datos/Entrada/` traen
  datos de pacientes y no se usan):
  - 10 generadas por la **opción 7 real** a partir de las entradas del golden (`tests/golden/entradas/opcion7_prefacturas/`),
    aplanadas en una carpeta. `EMPRESA GAMMA` sale en dos carpetas de facturador; la segunda se renombra
    `… (General sin factura).xlsx`. `NITs_consolidado.xlsx` se incluye para probar que el ETL lo excluye.
  - 9 casos dirigidos (misma plantilla de 23 columnas fijas) para las ramas que el golden no toca:
    `901000001` sedes y ciudades (SEDE 103, ZONA INDUSTRIAL, SEDE 103 en otra ciudad, EXTRAMURAL, MARIQUITA por id,
    ciudad fuera del mapa con cuenta PROVEEDORES, ciudad sin cuenta, código repetido AA10319, por palabra BUGA,
    producto gravado 100006, producto inexistente 999999, cobro doble, dos meses en `Base`, fila sin NIT);
    `900448167` NIT bloqueado; `901000002` empresa bloqueada por nombre; `901000003` dos terceros con el mismo
    `ref_num`; `901000004` nombre distinto al de Odoo; `901000005` plantilla sin columna `NIT`;
    `901000006` sin líneas; `12345` NIT inválido; segundo archivo de `900111111` (mismo NIT en dos archivos).
- `odoo.json`: el estado de Odoo simulado (terceros, productos, impuestos, UdM, cuentas analíticas).

Regenerar (solo con un cambio aprobado; cambia las referencias): `python tests/paridad/construir_entradas.py --forzar`.

## Captura

```bash
ETL_PY=/home/santiagosoa/Desarrollo/ETL-Avancys/venv/bin/python   # pandas 3.0.5, openpyxl 3.1.5, rapidfuzz 3.14.6
$ETL_PY -B tests/paridad/capturar_referencia.py /tmp/etl_run1
$ETL_PY -B tests/paridad/capturar_referencia.py /tmp/etl_run2
python3 tests/paridad/normalizar.py /tmp/etl_run1
python3 tests/paridad/normalizar.py /tmp/etl_run2
diff -r /tmp/etl_run1 /tmp/etl_run2      # debe salir vacío
```

`-B` evita escribir `.pyc` en el venv del ETL.

## Qué se exporta y orden estable

| Archivo | Contenido | Orden |
|---|---|---|
| `odoo_escrituras.json` | Cada `create` (valores completos de `account.move` con sus líneas) y cada `write` enviados a Odoo, con `nit`, `id` y `orden_llamada` | Por `nit` del tercero y luego `orden_llamada`. Las líneas de cada factura conservan el orden del ETL (es parte del contrato, T22) |
| `salida/log_inyeccion.xlsx.json` | Todas las hojas del libro, valores por fila e hipervínculos | Orden de filas del libro (el ETL lo deriva de los archivos ordenados por nombre: determinista) |
| `salida/pendientes_facturador.xlsx.json`, `salida/cuentas_por_revisar.xlsx.json` | Ídem | Ídem |
| `salida/facturas_creadas.csv`, `salida/log_inyeccion.txt` | Copia literal | Orden del ETL |
| `salida/verificar.json` | Archivos copiados a `Salida/verificar/` con SHA-256 (16 car.) | Por nombre |

Los `.xlsx` se vuelcan a JSON porque el binario cambia en cada escritura (fechas internas del zip).

## Normalizaciones (`normalizar.py`)

Se compararon dos corridas idénticas (2026-11-09, 08:58:47 y 08:59:06). `diff -r` sin normalizar mostró
**un solo campo variable, la fecha/hora de ejecución**, en dos lugares. Solo esos se normalizan:

| # | Dónde | Qué varía | Reemplazo | Por qué es seguro |
|---|---|---|---|---|
| N1 | `salida/log_inyeccion.txt`, prefijo de cada línea | `AAAA-MM-DD HH:MM:SS` del `asctime` del logging (`Pipeline.py:520`) | `<FECHA_HORA> \|` | Es el reloj de la corrida; el mensaje que sigue no se toca |
| N2 | `salida/log_inyeccion.xlsx.json`, hoja `Log Inyeccion`, columna `Fecha/Hora` | `datetime.now()` por archivo ilegible y por empresa (`Pipeline.py:1787`, `1795`) | `<FECHA_HORA>` | Ídem; solo celdas que cumplen exactamente el formato |

No hizo falta normalizar:
- **Ids**: el simulador se reinicia y numera desde 9001; aparecen iguales en `odoo_escrituras.json`, el CSV, los enlaces y el log.
- **Orden**: igual en ambas corridas (no depende de hash ni de tiempos).
- **Rutas**: la carpeta de trabajo es fija (`/tmp/etl_paridad_trabajo`).
- **Fecha del día en la guarda anti-duplicados** (`Pipeline.py:1259`): solo filtra la búsqueda en el simulador, que
  empieza vacío; no llega a ninguna salida.

## Supuestos del simulador (no verificados contra un Odoo real)

Los del golden (`tests/golden/_odoo_simulado.py`), más:
- `account.analytic.account` se ordena por `id` (en Odoo real el orden por defecto puede ser otro). Solo
  afecta qué cuenta llega primero cuando un código está repetido; el ETL desempata por nombre.
- `write` actualiza el registro y devuelve `True`; `create_date` se guarda en UTC.

Para validar el simulador contra la instancia de pruebas real, ver `docs/etl-analisis.md` §8 (requiere autorización).

## Observaciones de la corrida (comportamiento real del ETL, no corregido)

- Fila EXTRAMURAL con ciudad `BOGOTA` (sin "D.C."): queda **apartada**. El índice por nombre tiene la clave
  `BOGOTADC` y ni la coincidencia por palabra ni WRatio ≥ 95 la alcanzan, aunque `BOGOTA` sí esté en `CIUDAD_CUENTA`.
- NIT con dos terceros: el log dice primero "coincide con varios terceros" y luego "Sin tercero con N. identificacion".
- `GUADALAJARA DE BUGA` resuelve por palabra a `BUGA`, pero avisa "El codigo AA10460 del mapa no es de…"
  porque compara el nombre completo de la ciudad con el de la cuenta.

## Prueba de paridad (`test_paridad.py`)

`pytest tests/paridad -v` ejecuta la opción 5 real (`LoadPreInvoicesToOdoo` con sus adaptadores) sobre
`entradas/prefacturas/` contra el mismo `OdooParidad`, exporta igual que `capturar_referencia.py`, aplica N2 y
compara con `esperado/`: `odoo_escrituras.json`, los tres libros y `facturas_creadas.csv` iguales exactos, y
`verificar/` con los mismos archivos sin cambios. `log_inyeccion.txt` no se compara: la integración escribe el
log técnico en `logs.log` (diferencia aceptada, `docs/diseno-integracion.md`).

`PARIDAD_ESPERADO=<carpeta>` compara contra otra captura (por ejemplo, una nueva en `/tmp`).

`verificar_lector.py` (con el intérprete del ETL) compara el lector sin pandas con `pd.read_excel` sobre cualquier
carpeta: el 2026-11-23 dio 0 diferencias en las 19 entradas y en las 315 pre-facturas reales de `ETL-Avancys/datos/Entrada/`.
Ese mismo día, con un Odoo simulado sintético para esas 315 pre-facturas, ETL e integración produjeron salidas
idénticas (548 escrituras, 274 facturas, 41 VERIFICAR; datos solo en `/tmp`, borrados después).
