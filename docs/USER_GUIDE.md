# Guía de Usuario — Facturación SOANDES

> **Para:** facturadores y coordinadores de SOANDES · **Actualizada:** 2026-10-10
> Detalle técnico en la [Documentación Técnica](TECHNICAL_DOCUMENTATION.md).

## Índice

1. [¿Qué hace el sistema?](#1-qué-hace-el-sistema)
2. [Antes de empezar](#2-antes-de-empezar)
3. [El menú principal](#3-el-menú-principal)
4. [El ciclo mensual paso a paso](#4-el-ciclo-mensual-paso-a-paso)
5. [Cada opción en detalle](#5-cada-opción-en-detalle)
6. [Cómo leer el CONSOLIDADO](#6-cómo-leer-el-consolidado)
7. [Reportes que debes revisar](#7-reportes-que-debes-revisar)
8. [Preguntas frecuentes y problemas comunes](#8-preguntas-frecuentes-y-problemas-comunes)
9. [Glosario](#9-glosario)

---

## 1. ¿Qué hace el sistema?

El sistema automatiza la facturación mensual de exámenes médicos ocupacionales. A partir de tus libros de Excel:

1. Verifica que el NIT y el nombre de cada empresa sean correctos (en Odoo/Avancys y en el RUES).
2. Carga los facturadores. Las tarifas, los paquetes de cada empresa y el catálogo de CUPs se mantienen fuera de esta aplicación (Odoo y la base de datos).
3. Asigna a cada examen de cada paciente la tarifa que le corresponde: toma primero la **tarifa oficial de la empresa en Odoo** (tarifa especial y, si no, tarifa base) y, si Odoo no tiene precio, usa las tarifas cargadas en la base de datos según la empresa, la ciudad, el paquete y el tipo de actividad (INTRA/EXTRA).
4. Genera el **CONSOLIDADO.xlsx** y las **pre-facturas** separadas por facturador y por empresa.

**Principio clave: el sistema verifica, nunca crea.** Si no encuentra una empresa, no la inventa: la deja en un reporte para que la revises a mano. De Odoo **solo lee**: nunca crea ni modifica nada allí.

## 2. Antes de empezar

### 2.1 Abrir el sistema

En una terminal, desde la carpeta del proyecto:

```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
python main.py
```

### 2.2 Configuración (archivo `.env`)

La configura normalmente el equipo técnico una sola vez. Lo que te conviene saber:

| Variable | Para qué sirve |
|---|---|
| `DAY_INITIAL` / `DAY_FINAL` | Rango de días del mes. **Fuera** de ese rango, la opción 3 pide también el libro de facturas |
| `BOOK_ROUTE` / `BOOK_NAME` | Carpeta y nombre del libro que usa la opción 1 (Web Scrapping) |
| `TIAN_NIT` | NIT al que se facturan las empresas de la lista TIAN |
| `DIRECTORY` | Carpeta donde se guardan `data.json` y el log técnico (por defecto, la carpeta del proyecto) |
| `ODOO_USERNAME` / `ODOO_API_KEY` | Acceso a Odoo; sin ellos el sistema valida solo con la BD y el RUES, y la opción 3 usa solo las tarifas de la base de datos |

> ⚠️ Si `DAY_INITIAL` o `DAY_FINAL` están vacías, la opción 3 falla con *"Ocurrió un error ejecutando la opción. Revisa los logs."*

### 2.3 Consejos generales

- **Cierra en Excel los archivos** que el sistema va a leer o escribir (CONSOLIDADO, logs). Si están abiertos, la escritura puede fallar.
- Cuando el sistema pide una **ruta**, escribe la ruta completa del archivo, incluida la extensión `.xlsx`, por ejemplo `/home/usuario/Descargas/tarifas.xlsx`. Si el archivo no existe o no es Excel, verás *"Archivo inválido, intente de nuevo"* y te la volverá a pedir.
- Cuando pide una **hoja**, primero muestra *"Hojas disponibles:"*. Escribe el nombre **exactamente igual**: el sistema no lo valida, y un nombre mal escrito termina en error.
- Los **encabezados** de las columnas deben coincidir con los de esta guía. Los espacios al inicio o al final no importan.
- Si una opción falla, el sistema vuelve al menú y deja el detalle en los logs (ver §7).

## 3. El menú principal

```
 Opción  Descripción
   1     Web Scrapping
   2     Facturadores
   3     Asignar Tarifas
   4     Generar Pre Facturas
   5     Cargar Pre Facturas
   6     Empresas Facturadas a Otro NIT
   0     Salir
```

Escribe el número y presiona Enter. Si presionas Enter sin escribir nada, se elige **0 (Salir)**.

> **Importante:** al terminar cada opción, el programa muestra en la consola un resumen y, si hubo hallazgos por corregir, la carpeta donde quedaron sus libros de Excel. Copia ese resumen si lo necesitas: la consola no se guarda.

## 4. El ciclo mensual paso a paso

Cada paso usa lo que dejó el anterior. Este es el orden recomendado:

| # | Opción | ¿Cuándo? | Resultado principal |
|---|---|---|---|
| 1 | **1 · Web Scrapping** | Cuando hay empresas nuevas o dudosas | Empresas verificadas + `empresas_no_encontradas.xlsx` (es la única opción que retira de ese reporte las empresas ya resueltas) |
| 2 | **2 · Facturadores** | Cuando cambian las asignaciones gestor↔empresa | Facturador de cada empresa + hallazgos en `logs/facturadores/` |
| 3 | **3 · Asignar Tarifas** | **Cada mes** | **`CONSOLIDADO.xlsx`** + resumen en consola + `logs/asignar_tarifas/` (revisa `sin_resolver.xlsx`) |
| 4 | **4 · Generar Pre Facturas** | Tras revisar el CONSOLIDADO | Carpeta `pre-facturas/` |

> Los pasos 1 y 2 no son obligatorios cada mes; dependen de si cambiaron empresas o asignaciones. El paso 3 sí se ejecuta todos los meses. Las tarifas y los paquetes de cada empresa se mantienen fuera de esta aplicación (Odoo y la base de datos).

## 5. Cada opción en detalle

### Opción 1 — Web Scrapping

**Para qué:** confirmar que el NIT y el nombre de cada empresa son correctos y corregir NITs mal digitados.

**No pregunta nada.** Lee el libro indicado en `BOOK_ROUTE` / `BOOK_NAME`:

| Hoja | Columna | ¿Obligatoria? |
|---|---|---|
| `nits` | `nits` | Sí |
| `nits` | `empresa` | Recomendada: sin ella solo se busca por NIT y no se pueden corregir NITs errados |

**Cómo busca cada empresa**, en este orden: **Odoo** (por NIT y por nombre) → base de datos local → RUES (por NIT y por nombre). **Odoo es la fuente de verdad**: se consulta siempre, también para las empresas que ya están en la base de datos local. La base local solo es respaldo y se **corrige con lo que dice Odoo**: si una empresa no estaba, se agrega; si cambió su razón social en Odoo, se actualiza. En Odoo el NIT se busca en el campo *Número de identificación* y, si no está, en el NIT tributario (`vat`). Lo que no aparece en ninguna fuente queda pendiente de revisión manual. El sistema solo **lee** de Odoo; nunca lo modifica.

**Resultado:**

- `data.json`: guarda los resultados de la corrida. La opción 2 solo reutiliza de él lo que vino de RUES (para no repetir consultas lentas); Odoo se vuelve a consultar siempre. No lo edites a mano.
- `logs/web_scrapping/<fecha>/bd_local_actualizada.xlsx`: empresas que se agregaron o se corrigieron en la base local con los datos de Odoo (columnas: NIT, Nombre en BD local, Nombre en Odoo, Acción). Revísalo si quieres confirmar los cambios.
- `logs/empresas_no_encontradas.xlsx`: ver §7.

**Mensajes que puedes ver:**

| Mensaje | Qué hacer |
|---|---|
| *Odoo no disponible: se validó con la BD local y RUES.* | Revisa la conexión o las credenciales de Odoo y vuelve a ejecutar. Mientras tanto el proceso continúa con la base local y RUES, y **no** corrige la base local |
| *N empresa(s) quedaron sin consulta por nombre en RUES por el límite configurado* | Vuelve a ejecutar la opción para procesar las restantes |
| *Se corrigieron datos de la empresa '…'; revisa empresas_no_encontradas.xlsx.* | Solo aparece para empresas que existen en RUES y **faltan en Odoo**: confirma la corrección en ese reporte. Si Odoo o la base local ya tienen la empresa, no se muestra aviso (el cambio en la base local queda en `bd_local_actualizada.xlsx`) |

> Requiere Firefox instalado para Playwright (lo instala el equipo técnico) y puede tardar varios minutos.

### Opción 2 — Facturadores

**Para qué:** registrar qué facturador (gestor) atiende a cada empresa.

**Te pedirá:**

1. `Ruta completa del archivo Excel`
2. `Nombre de la hoja a procesar`

**Columnas requeridas:** `GESTOR`, `NIT`, `EMPRESA`. Las filas con alguna de ellas vacía se ignoran.

**Ten en cuenta:**

- Cada empresa tiene **un solo** facturador. Si aparece dos veces con facturadores distintos, gana la **última** fila y el conflicto queda en `vinculacion_duplicada.xlsx` con el facturador **descartado** y el **vigente**. Si se repite con el **mismo** facturador, no es conflicto.
- El nombre del gestor se compara de forma aproximada con los facturadores ya registrados, así que pequeñas diferencias de escritura no crean un facturador nuevo.
- Todas las empresas del Excel se verifican en Odoo, también las que ya están en la base local: el nombre de la empresa sale de Odoo. Si cambió, se corrige en la base local y queda en `bd_local_actualizada.xlsx`.
- Conviene ejecutar antes la opción 1.

**Al terminar** verás *"Hallazgos en logs/facturadores/<fecha>: …"* o *"Sin hallazgos."*. Los libros de esa carpeta:

| Libro | Qué significa |
|---|---|
| `empresa_no_encontrada` (NIT, Facturador) | La empresa no existe ni se pudo verificar; revísala |
| `facturador_no_encontrado` (NIT, Facturador) | El gestor no corresponde a ningún facturador registrado |
| `vinculacion_duplicada` (NIT, Empresa, Facturador descartado, Facturador vigente) | La empresa venía con dos facturadores; confirma cuál es el correcto |
| `bd_local_actualizada` (NIT, Nombre en BD local, Nombre en Odoo, Acción) | Empresas agregadas o corregidas en la base local con datos de Odoo |

| Mensaje | Qué significa |
|---|---|
| *Ya existe una empresa con el nombre '…' (NIT …). Se omite.* | Posible empresa duplicada con otro NIT; revísala en la base de datos |

### Opción 3 — Asignar Tarifas ⭐

**Para qué:** es el paso central del mes. Toma el consolidado de atenciones y le pone a cada examen la tarifa correcta: primero la de Odoo (tarifa especial y, si no, tarifa base) y, si Odoo no tiene precio, la de la base de datos.

**Te pedirá:**

1. `Ruta del Excel de TARIFAS (consolidado)`: el libro con las atenciones del mes.
2. `Nombre de la hoja a procesar`.
3. **Solo si hoy está fuera del rango `DAY_INITIAL`–`DAY_FINAL`:**
   - `Ruta del Excel con NÚMEROS DE FACTURA`
   - `Nombre de la hoja a procesar`

   Dentro del rango no te los pide y la columna `FACTURAS` sale vacía.

**Columnas del libro de atenciones:**

| Columna | Notas |
|---|---|
| `NIT`, `Empresa`, `Empresa Misión`, `Sede` | Identificación de la empresa |
| `Ciudad`, `Medio de Pago`, `Tipo Examen`, `Cargo`, `Paciente`, `Fecha Ingreso`, `N° Identificación` | Datos de la atención |
| `TIPO DE ACTIVIDAD` | `INTRAMURAL`/`EXTRAMURAL`; si está vacía se toma INTRA |
| `Base` | Opcional, pero necesaria para el aprendizaje automático de i-medical |
| Columnas CUP (`890201`, `890201-1`, …) | Pon **`1`** en la celda si el examen se realizó |

**Columnas del libro de facturas:** `N° Identificación` y `# FACTURA`. Si un paciente tiene varias facturas, se unen con coma.

**Resultado:**

- `CONSOLIDADO.xlsx` en la carpeta del proyecto. Se sobrescribe en cada ejecución. Ver §6 para leerlo.
- Una tabla resumen en la consola con cuántas celdas salieron de cada origen (ver *Resumen al terminar*).
- La carpeta `logs/asignar_tarifas/<fecha>/` con los libros de hallazgos (ver §7).

**Tratamientos especiales automáticos:**

- **i-medical.** Corrige NITs que se sabe que llegan mal desde i-medical. Además aprende correcciones nuevas cuando la columna `Base` dice IMEDICAL y Odoo confirma el NIT correcto. El detalle queda en el log técnico (`logs.log`).
- **TIAN.** Las empresas de la lista TIAN se facturan al NIT de TIAN, con el nombre terminado en `(TIAN)`. Revisa `empresas_tian.xlsx`; si falta configurar `TIAN_NIT`, no se redirigen y el aviso queda solo en `logs.log`.
- **Nombres unificados.** Si un mismo NIT llega con varios nombres, se usa uno solo: primero el de Odoo, luego el de la base de datos.
- **Fechas.** `Fecha Ingreso` queda en formato dd/mm/aaaa. Si el día y el mes vienen invertidos, se corrigen. Las fechas futuras o de más de 3 meses de antigüedad se registran en el log técnico (`logs.log`).
- **Valores por defecto.** Empresa sin facturador → `GENERAL`. La columna `PAQUETE` muestra la tarifa especial de Odoo; si no tiene, la tarifa base de Odoo; si tampoco, el paquete de la base de datos (por defecto `PAQUETE C 2025`).

**Resumen al terminar.** La opción 3 no muestra avisos durante el proceso (solo las barras de progreso); al final imprime una tabla *Asignación de tarifas*:

| Fila de la tabla | Qué cuenta |
|---|---|
| *Tarifa Odoo (especial/base)* | Celdas con el precio oficial de Odoo |
| *Fase 1* … *Fase 6* | Celdas resueltas con las tarifas de la base de datos (ver §6) |
| *Sin resolver (valor 1)* | Exámenes sin tarifa |

Debajo de la tabla verás:

- *Hallazgos por fase en: logs/asignar_tarifas/<fecha>* → revisa esa carpeta (ver §7).
- *Sin hallazgos: no se generaron libros por fase.* → todo salió de Odoo.
- En amarillo, *Odoo no disponible: todas las tarifas salieron de la cascada local.* → revisa la conexión o las credenciales de Odoo y vuelve a ejecutar.

Las empresas que no se encontraron se **agregan** a `empresas_no_encontradas.xlsx`, pero esta opción nunca las retira de allí; para limpiar las ya resueltas, ejecuta la opción 1.

### Opción 4 — Generar Pre Facturas

**Para qué:** separar el CONSOLIDADO en un archivo por empresa, organizado por facturador.

**No pregunta nada.** Lee `CONSOLIDADO.xlsx` de la carpeta del proyecto y escribe en `pre-facturas/`:

```
pre-facturas/
├── <NOMBRE FACTURADOR>/
│   └── pre_factura_<NIT>_<Empresa>.xlsx
├── GENERAL/                  ← empresas GENERAL con factura que empieza por "SET"
├── General sin factura/      ← empresas GENERAL sin factura SET
├── SIN_FACTURADOR/           ← filas sin facturador
└── NITs_consolidado.xlsx     ← un solo libro con una hoja por empresa
```

Cada pre-factura tiene la hoja **BASE GENERAL** y la hoja **Leyenda**:

- La fila 1 muestra el **nombre** de cada examen.
- La fila 2 tiene los encabezados.
- Solo aparecen los exámenes que esa empresa usó.
- Se conservan los **colores** del CONSOLIDADO. La hoja Leyenda también explica que una celda sin color es tarifa de Odoo (todavía muestra una fila *Fase 7* que ya no se usa).

Si no existe el CONSOLIDADO, verás *"Archivo CONSOLIDADO.xlsx no encontrado. No se pueden generar pre-facturas."*: ejecuta primero la opción 3.

### Opción 5 — Cargar Pre Facturas (Odoo)

**Para qué:** crear en Odoo **una factura borrador por empresa** a partir de las pre-facturas. Hace exactamente lo mismo que el script ETL-Avancys (`Pipeline.py`) que se usaba hasta ahora.

**Antes de correrla, revisa `configuracion_inyeccion.xlsx`** (en la carpeta desde la que abres el sistema; otra ruta con `INYECCION_CONFIG_XLSX`). La primera vez el sistema lo crea con los valores que tenía el ETL y se detiene para que lo revises. Tiene tres hojas:

| Hoja | Columnas | Qué hace |
|---|---|---|
| `NITS_BLOQUEADOS` | NIT, MOTIVO | El NIT existe en Odoo pero apunta a otro tercero: no se factura (VERIFICAR) |
| `EMPRESAS_BLOQUEADAS` | NOMBRE, MOTIVO | Empresas que no se suben; basta con que el nombre **empiece** así |
| `YA_SUBIDAS` | NIT, FACTURA | **Vaciar cada mes.** Solo para repetir una corrida que se cortó a la mitad sin duplicar lo que ya entró |

**Te pedirá:** la carpeta con las pre-facturas a cargar (por ejemplo, una copia de las carpetas que genera la opción 4). Se leen los `.xlsx` de esa carpeta, sin subcarpetas; se ignoran `NITs_consolidado.xlsx` y los archivos temporales `~$`.

**Qué hace con cada empresa:**
- Busca el tercero en Odoo **solo por NIT** (`N. identificación`). Si no existe o hay más de uno → **VERIFICAR**; nunca crea terceros.
- Arma una línea por examen y cuenta analítica (cantidad = pacientes). La cuenta sale de la sede y la ciudad; si no se puede imputar con certeza, ese paciente **se aparta** (no se manda a Bogotá).
- Crea la factura **sin fechas**, en el diario de pre-facturas, con las dos autorretenciones. El precio queda en el de lista; se trae con el botón "Actualizar precios" de Odoo (o automáticamente si `ODOO_ACTUALIZAR_PRECIOS=true`).
- No duplica: si hoy ya creaste un borrador para ese cliente, lo reporta y no crea otro.

**Al terminar verás un resumen** (empresas OK, para verificar y con error) y la carpeta de la corrida, `logs/cargar_prefacturas/<AAAA-MM-DD_HHMM>/`, con:

| Archivo | Qué revisar |
|---|---|
| `log_inyeccion.xlsx` | Una fila por empresa con estado, detalle y enlace a la factura |
| `pendientes_facturador.xlsx` | Hoja *Subir a mano*: exámenes que quedaron por fuera (agregarlos a mano). Hoja *Empresas sin factura*: empresas que no se facturaron y qué hacer |
| `cuentas_por_revisar.xlsx` | Qué ciudades o productos arreglar en Odoo para la próxima corrida |
| `facturas_creadas.csv` | Ids de las facturas creadas en la corrida |
| `verificar/` | Copias de los archivos que no se pudieron leer (plantilla cambiada) |

### Opción 6 — Empresas Facturadas a Otro NIT

**Para qué:** registrar las empresas filiales que no se facturan con su propio NIT sino con el de otra empresa (TIAN, VISE, RSG, CLIP SALUD…). En la opción 3, sus atenciones pasan al NIT de destino y la empresa queda como `"<razón social>(<ETIQUETA>)"`, por ejemplo `AQUIA SAS(ASTAF)`; así toman el facturador, el paquete y las tarifas del destino.

**Te pedirá:** el Excel y la hoja. La hoja debe tener en la fila 1:

| NIT_ORIGEN | NIT_DESTINO | ETIQUETA | NOMBRE (opcional) | ACTIVO (opcional) |
|---|---|---|---|---|
| 101907357 | 860507033 | VISE | DEAS LTDA ROLLS | |
| 830121897 | 830068110 | ASTAF | AQUIA SAS | |
| 900111111 | | | | NO |

- **NIT sin dígito de verificación.** Los puntos, guiones y espacios se ignoran.
- **ETIQUETA** es el sufijo que se agrega al nombre (máximo 50 caracteres; usa nombres cortos: `TIAN`, `VISE`, `RSG`).
- **Solo agrega o actualiza:** las empresas que ya estaban cargadas y no vienen en el archivo se quedan como estaban. Para **quitar** una, pon su NIT_ORIGEN con `ACTIVO = NO`.
- Si un NIT_ORIGEN aparece dos veces, gana la **última** fila.

**Requisito del destino:** la empresa de destino debe existir en la base, tener paquete y, para que sus pre-facturas no salgan en GENERAL, facturador. Si no, la fila se carga igual pero se avisa.

**Al terminar verás un resumen** (nuevas, actualizadas, desactivadas, con error) y, si hubo algo que revisar, una carpeta `logs/redirecciones/<AAAA-MM-DD_HHMM>/` con:

| Libro | Qué significa |
|---|---|
| `filas_con_error` | Filas que **no** se cargaron: NIT vacío o con letras, sin etiqueta, etiqueta muy larga, origen igual al destino o el NIT de TIAN como origen |
| `filas_repetidas` | NIT_ORIGEN repetido: qué fila quedó |
| `destinos_por_revisar` | Destinos que no existen en la base, sin paquete (sus empresas no se redirigen hasta corregirlo) o sin facturador (salen en GENERAL) |
| `origenes_en_tian` | NIT que también están en la tabla `tian`: TIAN tiene prioridad mientras sigan allí |
| `desactivadas` | Filas con `ACTIVO = NO` y si estaban activas |

## 6. Cómo leer el CONSOLIDADO

`CONSOLIDADO.xlsx` tiene la hoja **Consolidado** y, si hubo celdas coloreadas o con tarifa de Odoo, la hoja **Leyenda**.

**Columnas calculadas:**

| Columna | Contenido |
|---|---|
| `FACTURADOR` | Facturador asignado o `GENERAL` |
| `Especial / General` | `ESPECIAL` o `GENERAL` |
| `PAQUETE` | Tarifa especial de Odoo; si no, tarifa base de Odoo; si no, paquete de la base de datos o `PAQUETE C 2025` |
| `FACTURAS` | Número(s) de factura del paciente |
| `Total` | Suma de las tarifas de la fila |
| Columnas CUP | **Valor de la tarifa** asignada a cada examen |

**Colores: ¿de dónde salió cada tarifa?**

El sistema busca primero la tarifa de la empresa en Odoo (tarifa especial y luego tarifa base). Si Odoo no tiene precio para ese examen, ciudad y actividad, la busca en la base de datos, en este orden. El color indica de dónde salió:

| Color | Fase | De dónde salió la tarifa | ¿Revisar? |
|---|---|---|---|
| Sin color (con valor) | Odoo | Tarifa especial o tarifa base de la empresa en Odoo | No |
| 🟩 Verde claro `#E2EFDA` | 1 | Paquete propio de la empresa en la base de datos | Opcional |
| 🟨 Dorado suave `#FFF2CC` | 2 | `PAQUETE C 2025`, mismo examen y ciudad | Opcional |
| 🟧 Naranja `#F4B183` | 3 | Otro paquete cualquiera, mismo examen y ciudad | Sí |
| 🟦 Azul claro `#BDD7EE` | 4 | `PAQUETE C 2025`, examen base (sin sufijo `-1`, `-2`…) | Sí |
| 🔷 Azul medio `#9DC3E6` | 5 | Otro paquete, examen base, misma ciudad | Sí |
| 🟪 Púrpura `#D5A6E6` | 6 | Cualquier paquete de **otra ciudad** | Sí, con prioridad |
| Sin color y valor **1** | — | **No se encontró tarifa** (ver `sin_resolver.xlsx`) | **Obligatorio**: revisa `sin_resolver.xlsx` |

> Un **1** en una columna CUP no es una tarifa de $1: significa que el examen se hizo y no hay tarifa. No generes pre-facturas sin resolver esos casos.

## 7. Reportes que debes revisar

Todos quedan en la carpeta `logs/` salvo que se indique otra.

| Archivo | Lo genera | ¿Acumula? | Qué revisar |
|---|---|---|---|
| `empresas_no_encontradas.xlsx` | 1, 3 | Sí. Solo la opción 1 retira las empresas ya resueltas; la opción 3 solo agrega las que no encuentra | Columna **Estado**: *No encontrado (ni Odoo ni RUES)* · *Existe en RUES, falta en Odoo* (hay que crearla en Odoo antes de facturar). En las filas de RUES puede sumarse *NIT corregido* o *Nombre corregido*. Solo lista empresas que **no existen en Odoo**: las que Odoo ya tiene no aparecen, aunque se hayan corregido o no se hayan podido guardar en la base local (eso va a `bd_local_actualizada.xlsx`) |
| `empresas_tian.xlsx` | 3 | No | Empresas redirigidas a TIAN (tabla `tian`) en esta corrida |
| `empresas_redirigidas.xlsx` | 3 | No | Empresas redirigidas por la opción 6 (`billing_redirects`) en esta corrida |
| `logs/cargar_prefacturas/<fecha>/log_inyeccion.xlsx` | 5 | No (una carpeta por corrida) | OK · VERIFICAR · ERROR por empresa, con enlace a la factura |
| `logs/cargar_prefacturas/<fecha>/pendientes_facturador.xlsx` | 5 | No | Exámenes por subir a mano y empresas sin factura |

> Los archivos que **no acumulan** se reemplazan en cada ejecución. Si necesitas conservar uno, cópialo antes de volver a ejecutar la opción.

### Hallazgos por ejecución

Las opciones 1, 2 y 3 crean, en cada ejecución, una carpeta con **un libro por tipo de hallazgo**, para entregar cada libro al área que debe corregirlo. Solo se crean los libros que tienen filas: si no hubo hallazgos, no se crea carpeta y la consola dice *Sin hallazgos*.

| Carpeta (`logs/…/AAAA-MM-DD_HHMM/`) | Opción | Libros |
|---|---|---|
| `logs/web_scrapping/` | 1 | `bd_local_actualizada` (empresas agregadas o corregidas en la base local con los datos de Odoo; columnas NIT, Nombre en BD local, Nombre en Odoo, Acción) |
| `logs/facturadores/` | 2 | `bd_local_actualizada`, `empresa_no_encontrada`, `facturador_no_encontrado`, `vinculacion_duplicada` (empresa que aparece con dos facturadores: prevalece el **último** del Excel; el libro indica el facturador **descartado** y el **vigente**) |
| `logs/asignar_tarifas/` | 3 | `fase_01_paquete_propio_local` … `fase_06_cualquier_ciudad` y `sin_resolver` (una fila por paciente y examen, con el precio y su origen); `empresas_odoo` (Motivo: *No encontrada en Odoo* / *Sin tarifa especial ni base*). Las celdas con tarifa de Odoo no generan libro |

> Si ejecutas la misma opción dos veces en el mismo minuto, la segunda reemplaza los libros con el mismo nombre. Si necesitas conservarlos, copia la carpeta antes.

## 8. Preguntas frecuentes y problemas comunes

**"Ocurrió un error ejecutando la opción. Revisa los logs."**
La opción falló, pero el programa sigue abierto. Lee el mensaje de error que quedó en la consola; si no es claro, pásale al equipo técnico el archivo `logs.log`. Las causas más comunes son:

- Un nombre de hoja mal escrito.
- Falta una columna obligatoria.
- `DAY_INITIAL` / `DAY_FINAL` vacías.
- El archivo está abierto en Excel.

**Muchas celdas quedaron en 1 en el CONSOLIDADO.**
Faltan tarifas, o el paquete, la ciudad o la actividad de esa fila no existen en la base de datos. Revisa `sin_resolver.xlsx` y `empresas_odoo.xlsx` en `logs/asignar_tarifas/<fecha>/`; si la empresa no tiene tarifa en Odoo, pídele al administrador de Odoo que se la asigne. Las tarifas de la base de datos se mantienen fuera de esta aplicación; cuando estén corregidas, repite la opción 3.

**Una celda tiene valor y no tiene color.**
Es el precio oficial de la empresa en Odoo (tarifa especial o tarifa base).

**La columna PAQUETE muestra un nombre distinto al de la base de datos.**
Es el nombre de la tarifa de la empresa en Odoo, que tiene prioridad.

**La consola dijo *Odoo no disponible*.**
Todas las tarifas salieron de la base de datos. Revisa la conexión o las credenciales de Odoo y vuelve a ejecutar la opción 3.

**Una empresa sigue en `empresas_no_encontradas.xlsx` aunque ya la encuentra.**
La opción 3 solo agrega empresas a ese reporte. Ejecuta la opción 1 con ese NIT para retirarla, o bórrala a mano.

**Una empresa aparece con un NIT distinto al que escribí.**
El sistema lo corrigió con Odoo, el RUES o la tabla i-medical. Si la empresa viene de RUES (no existe en Odoo), la corrección queda en `empresas_no_encontradas.xlsx` como *NIT corregido*; si viene de Odoo, ya no se lista allí y la opción 1 solo la muestra en la consola.

**Una empresa que sí existe en Odoo ya no aparece en `empresas_no_encontradas.xlsx`.**
Es lo esperado: ese libro se entrega al área que crea empresas en Odoo y solo lista las que faltan allí. Si la base local no pudo actualizarse con los datos de Odoo, lo verás en `bd_local_actualizada.xlsx` (*No actualizada: nombre duplicado en BD local* o *No actualizada: error al guardar*) y en la consola, no en ese libro.

**Una empresa sale con "(TIAN)" en el nombre.**
Está en la lista TIAN y se factura al NIT de TIAN. Revisa `empresas_tian.xlsx`.

**La columna FACTURAS salió vacía.**
Hoy está dentro del rango `DAY_INITIAL`–`DAY_FINAL`, así que el sistema no pidió el libro de facturas.

**¿Puedo repetir una opción?**
Sí. Todas las cargas actualizan los datos en lugar de duplicarlos. El CONSOLIDADO y las pre-facturas se regeneran.

**La opción 1 tarda mucho.**
Es normal: consulta el RUES empresa por empresa. Si se corta por el límite de consultas por nombre, ejecútala de nuevo.

## 9. Glosario

| Término | Significado |
|---|---|
| **CUP** | Código Único de Procedimiento: identifica cada examen (p.ej. `890201`). Con sufijo (`890201-1`) es una variante que puede homologarse al código base |
| **NIT** | Identificación tributaria de la empresa. El sistema lo guarda con 9 dígitos, sin dígito de verificación |
| **DV** | Dígito de verificación del NIT |
| **Paquete** | Conjunto de tarifas pactado con una empresa, en la base de datos local. `PAQUETE C 2025` es el paquete de referencia por defecto |
| **Tarifa especial / Tarifa base (Odoo)** | Tarifas asignadas a cada empresa en su ficha de Odoo. Son la fuente principal de precios de la opción 3: primero la especial, luego la base |
| **Hallazgo** | Fila que el sistema no pudo procesar o resolvió con un respaldo, y que queda en un libro de `logs/<opción>/<fecha>/` para que el área correspondiente la corrija |
| **Proveedor / Tarifa especial** | Otros tipos de contrato tarifario, además de los paquetes |
| **INTRA / EXTRA** | Examen intramural (en sede) o extramural (fuera de sede); cambian la tarifa |
| **Facturador / Gestor** | Persona responsable de facturar a una empresa |
| **GENERAL** | Empresas sin facturador asignado |
| **CONSOLIDADO** | Libro con todas las atenciones del mes y sus tarifas |
| **Pre-factura** | Libro por empresa listo para revisar y facturar |
| **i-medical** | Tabla de correcciones de NITs que llegan mal desde i-medical |
| **TIAN** | Lista de empresas que se facturan a nombre de TIAN |
| **RUES** | Registro Único Empresarial y Social: fuente pública para verificar empresas |
| **Odoo / Avancys** | ERP donde se emiten las facturas y donde está la tarifa oficial de cada empresa (fuente principal de precios de la opción 3) |
