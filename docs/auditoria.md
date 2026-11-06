# Auditoría de Facturacion

> Auditoría de solo lectura del 2026-11-05 sobre `master` (`3b022f1`). No se modificó código.
> Alcance: `main.py`, todo `src/`, `migrations/`, `requirements.txt` y las pruebas. Se usó `ETL-Avancys/Pipeline.py` solo como referencia (solo lectura).
> Línea base de pruebas: 951 pasan y 4 fallan (ver AUD-54 y `CLAUDE.md`).
> ✔ junto al ID = verificado leyendo directamente el código o ejecutando la función. El resto viene del análisis
> completo por módulo, con cita de archivo:línea. Hay que confirmarlo antes de actuar.

---

## Mapa del sistema

### Puntos de entrada
| Entrada | Archivo | Notas |
|---|---|---|
| CLI interactiva | `main.py` → `console_app()` | Menú Rich; `dispatch_option` llama al controller; `safe_dispatch` contiene cualquier excepción (main.py:106-120) |
| Migraciones | `alembic upgrade head` → `migrations/env.py` | Acepta `DATABASE_URL`; la app no (AUD-45) |
| Pruebas | `pytest` | Fakes manuales en `tests/fakes/` (ADR-005) |

No hay API HTTP, ni tareas programadas, ni otro punto de entrada.

### Módulos (hexagonal: `domain` / `application/use_cases` / `infrastructure`)
| Opción | Módulo | Controller | Lee | Escribe |
|---|---|---|---|---|
| 1 Web Scrapping | `scrapping` | `import_rues_nits.py` | `BOOK_ROUTE/BOOK_NAME` hoja `nits`; Odoo `res.partner`; BD `companies`; RUES (Playwright) | `companies`; `logs/empresas_no_encontradas.xlsx` (histórico); `logs/web_scrapping/<ts>/bd_local_actualizada.xlsx`; `<DIRECTORY>/data.json` |
| 2 Facturadores | `billers` | `import_billers_controller.py` | Excel `GESTOR, NIT, EMPRESA`; cascada NIT | `billers`, `companies`, `companies_billers` |
| 3 Tratamiento Información (@deprecated) | `dataProcessing` | `import_information_controller.py` | Excel con hojas `Paquetes`, `Proveedores` y `TarifasEspeciales*`; BD `cups` | `facturacion_normalizada.xlsx`; `logs/novedades_cups.xlsx` |
| 4 Cargar Tarifas (@deprecated) | `rates` (+ package/provider/special/city/cup/activity) | `import_rates_controller.py` | Libro de la opción 3 | `cities, packages, providers, specials, rates`; `logs/cargar_tarifas/<ts>/` |
| 5 Registrar Empresas-Paquetes (@deprecated) | `company` | `import_companies_rates_controller.py` | Excel `NIT, RAZON SOCIAL, PAQUETE`; cascada NIT | `companies`, `companies_packages`; `logs/registrar_empresas/<ts>/`, `logs/empresas_no_vinculadas.xlsx` |
| 6 Asignar Tarifas | `assign` | `assigned_rates_controller.py` | Excel consolidado de atenciones; libro de facturas (fuera de la ventana de días); Odoo (partners y tarifas); BD (12 tablas); `data.json` | `CONSOLIDADO.xlsx` (cwd); `logs/asignar_tarifas/<ts>/`; tabla `imedical`; log TIAN; log de no encontrados |
| 7 Generar Pre Facturas | `preInvoice` | `pre_invoice_controller.py` | `CONSOLIDADO.xlsx`; BD `cups` | `pre-facturas/<facturador>/pre_factura_<NIT>_<Empresa>.xlsx`; `pre-facturas/NITs_consolidado.xlsx` |
| 8 Cargar Pre Facturas (**desconectada**, main.py:89-91) | `odooInjection` | `inject_invoices_controller.py` | `pre-facturas/General sin factura/*.xlsx` | Odoo `account.move` (draft); `odoo-output/log_inyeccion.xlsx` |
| 9 Generar Faltantes (@deprecated) | `assign` | `missing_rates_controller.py` | CONSOLIDADO | `faltantes.xlsx` |
| 10 Detectar Duplicados | `company` | `detect_duplicates_controller.py` | BD `companies` | `logs/empresas_duplicadas.xlsx` |

`src/shared/` contiene la BD (`database.py`, `models.py`), Excel I/O, consola (`USER_CONSOLE`), logging (`LoggerAdapter`, `TechOnlyLogger`), reporting (`FindingsWriter`), utilidades (`text_normalizer`, `document_normalizer`, `rapidfuzz_biller`, `mega_dataframes`) y `config.py`.

### Flujo de una factura (de la entrada de datos a la salida)
```
[Excel NITs] ─1─► companies (BD) ◄──── Odoo res.partner (solo lectura) / RUES
[Excel facturadores] ─2─► billers + companies_billers
[Excel tarifario] ─3─► facturacion_normalizada.xlsx ─4─► cities/packages/providers/specials/rates (BD)
[Excel empresas-paquete] ─5─► companies_packages

[Excel atenciones] + [Excel facturas*] ─6─►  CONSOLIDADO.xlsx  (precio por celda CUP, Total)
      1. i-medical (corrige NIT) → normaliza NIT a 9 dígitos
      2. Empresa: Odoo NIT → Odoo nombre → BD NIT → BD nombre → RUES NIT → RUES nombre → NOVEDAD
      3. Normaliza fechas/texto/actividad → TIAN (redirige NIT) → ciudad (fuzzy)
      4. Tarifas Odoo (especial → base) → facturador → paquete
      5. Precio: Odoo; si no, cascada local de fases 1-6; si no, la celda queda en 1
      6. Total = suma de las celdas CUP → FACTURAS (join con el libro de facturas)
                                        │
                                        ▼ 7
             pre-facturas/<FACTURADOR | GENERAL | General sin factura | SIN_FACTURADOR>/pre_factura_<NIT>_<Empresa>.xlsx
                                        │  (copia manual: pregunta P-14)
                                        ▼
       ETL-Avancys/Pipeline.py (producción)   |   opción 8 (desconectada, versión antigua del ETL)
              Odoo account.move out_invoice en estado draft, price_unit = list_price de Odoo
              impuestos (2 autorretenciones 2%) y numeración: los calcula/asigna Odoo
```
\* El libro de facturas solo se pide fuera de la ventana `DAY_INITIAL`–`DAY_FINAL` (main.py:81-84).

**Hecho clave:** Facturacion **no calcula impuestos, IVA, retenciones ni numeración de facturas**. El precio que calcula la opción 6 sirve para revisión y pre-factura. La factura en Odoo usa `list_price` del producto (`inject_invoices_to_odoo.py:169`; también en ETL, `Pipeline.py:1183`). Los impuestos los calcula Odoo con los `tax_ids` enviados, y el consecutivo lo asigna Odoo al confirmar el borrador.

### Esquema de BD (resumen)
- `rates`: PK compuesta `(rateable_id, city_id, cup_id, activity_id, rateable_type)`, polimórfica (package/provider/special). `rate BigInteger` es el **único monto** del esquema (pesos enteros).
- `companies (nit String(12) único)`, `companies_billers` (un facturador por empresa), `companies_packages` (un paquete por empresa).
- `imedical (nit_error → nit_success)`, `tian`, `cups (code String(9))`, `type_activities` (CHECK INTRA/EXTRA).
- Solo en migraciones: `roles, permissions, role_permissions, users` (RBAC sin modelo ni uso).

---

## Reglas de negocio

### Impuestos y totales
| Archivo:línea | Regla |
|---|---|
| `src/odooInjection/config.py:29-37` | Impuestos fijos en todas las líneas: "AUTORRETENCION IMPUESTO RENTA 2%" y "AUTORRETENCION COMPRA IMPUESTO RENTA 2%". Los calcula Odoo |
| `src/odooInjection/infrastructure/odoo/xmlrpc_odoo_repository.py:293-302` | Si el nombre exacto del impuesto no existe: `ilike name[:20]`, toma el primero de hasta 5 |
| `src/odooInjection/application/use_cases/inject_invoices_to_odoo.py:173-174` | Si no se encuentra ningún impuesto, la línea se envía sin impuestos (solo un warning) |
| `inject_invoices_to_odoo.py:158-162` | Cuenta de ingresos gravados (42650) si el producto está en `productos_gravados` ("100006"); si no, excluidos (42653) |
| `inject_invoices_to_odoo.py:146-147, 169` | Cantidad = nº de pacientes por (examen, cuenta analítica); `price_unit = list_price` de Odoo |
| `src/assign/application/use_cases/assigned_rates.py:1531-1536` | `Total = sum_horizontal` de todas las columnas CUP, incluidas las celdas sin resolver que valen 1; sin columnas CUP, Total = 0 |

### Montos y redondeos
| Archivo:línea | Regla |
|---|---|
| `src/assign/domain/odoo_rate_index.py:39` | Los precios de Odoo ≤ 0 se ignoran |
| `odoo_rate_index.py:47` ✔ | Precio de Odoo **truncado** con `int(price)` al construir el índice; ante claves duplicadas gana la primera (`setdefault`) |
| `assigned_rates.py:1314-1323, 1344, 1393, 1445, 1488` | Tarifa local `int(price)`; una tarifa 0 cuenta como inexistente y pasa a la fase siguiente |
| `assigned_rates.py:1128, 1247, 1309` | Solo se valoran las celdas CUP con valor exactamente 1 |
| `assigned_rates.py:1517` | Una celda sin tarifa queda en 1 en el CONSOLIDADO |
| `assigned_rates.py:287-290` | Formato "#,##0" solo en las celdas coloreadas |
| `src/dataProcessing/infrastructure/persistence/cup_column_validator.py:24-42` ✔ | VALOR (opción 3): quita espacios, NBSP y "$"; si len ≥ 7, toma lo que hay antes del primer "."; si no, quita los "."; respaldo `int(float)` (ver AUD-01) |
| `src/rates/application/use_cases/import_rates_from_excel.py:205, 268` ✔ | VALOR (opción 4): quita todo lo que no sea dígito y aplica `int()` (ver AUD-02) |
| `import_rates_from_excel.py:290-296`; `sa_rates_repository.py:138-141` | Deduplica por la PK de `rates`; la última fila gana; el upsert sobrescribe `rate` |

### Prioridad y cascada de tarifas (opción 6)
| Archivo:línea | Regla |
|---|---|
| `assigned_rates.py:1130-1133` | En Odoo: tarifa especial antes que la base |
| `odoo_rate_index.py:6, 51-52` | Odoo solo se consulta para la actividad INTRA o EXTRA |
| `assigned_rates.py:1139` | Una tarifa vencida (`finish_date < hoy`) se asigna igual y se registra `odoo_tarifa_vencida` |
| `assigned_rates.py:1312-1517` | Cascada local: F1 paquete propio → F2 PAQUETE C 2025 → F3 cualquier fuente con la misma ciudad/CUP/actividad → F4 CUP base en PAQUETE C 2025 → F5 CUP base en cualquier paquete con la misma ciudad → F6 cualquier paquete y ciudad por CUP+actividad → sin resolver (1) |
| `assigned_rates.py:1060, 1176` | Paquete por defecto escrito a mano: "PAQUETE C 2025" |
| `assigned_rates.py:1255, 1383, 1420` | CUP base = texto antes del primer "-" |
| `assigned_rates.py:1094-1108` | La columna PAQUETE visible = nombre de la tarifa especial de Odoo; si no, la base de Odoo; si no, el paquete local |
| `assigned_rates.py:94-103` | Colores por fase: F1 E2EFDA, F2 FFF2CC, F3 F4B183, F4 BDD7EE, F5 9DC3E6, F6 D5A6E6; Odoo sin color |

### Empresas, NIT y facturador
| Archivo:línea | Regla |
|---|---|
| `src/shared/utils/text_normalizer.py:48-53` | `normalize_nit`: solo dígitos y los primeros 9 (el DV se descarta) |
| `assigned_rates.py:522-530` | Lo mismo en Polars (`slice(0, 9)`), aplicado antes y después del matching |
| `src/shared/utils/document_normalizer.py:38-55` | Opción 5: NIT si tiene 9-10 dígitos y empieza por 8/9 (DV DIAN módulo 11); si no, es cédula y se conserva entera |
| `src/billers/application/use_cases/import_billers_from_excel.py:88-91` | Opción 2: dígitos y `slice(0, 9)` sin distinguir cédula |
| `assigned_rates.py:562-709` | Cascada Odoo NIT → Odoo nombre → BD NIT → BD nombre → RUES NIT → RUES nombre → NOVEDAD (ADR-013) |
| `assigned_rates.py:423-437, 483-518, 595, 649, 681` | i-medical: `nit_error → nit_success`; el NIT corregido queda bloqueado frente a las ramas por nombre |
| `assigned_rates.py:550, 607-627` | Auto-registro i-medical si Base contiene "IMEDICAL" y la similitud de nombre es ≥ 90 |
| `assigned_rates.py:902-994` | TIAN: NIT → `TIAN_NIT`, Empresa → `"<nombre>(TIAN)"` sin espacio; aborta si falta `TIAN_NIT`, la empresa o su paquete |
| `assigned_rates.py:1018-1051` | Facturador por NIT; si no hay, "GENERAL"; "Especial / General" se deriva de FACTURADOR |
| `inject_invoices_to_odoo.py:131-137`; ADR-010 | Nunca crear clientes en Odoo; si no se encuentra, VERIFICAR |
| `src/company/application/use_cases/import_companies_from_excel.py:274-317`; `import_billers_from_excel.py:184-208` | Un paquete y un facturador por empresa; la última fila gana y se registra el hallazgo |
| `src/company/domain/.../duplicate_company_detector.py:56-92` | Duplicados: nombre idéntico agresivo `[A-Z0-9Ñ]`, o un NIT igual a otro más un dígito con token_sort ≥ 85 |

### Umbrales de fuzzy matching
| Archivo:línea | Umbral |
|---|---|
| `src/scrapping/infrastructure/console/import_rues_nits.py:38` | Nombre de empresa (opción 1): 90 (`COMPANY_NAME_MATCH_THRESHOLD`) |
| `src/shared/utils/rapidfuzz_biller.py:18-29` ✔ | `token_sort_ratio` y, si no alcanza, `partial_ratio` con el **mismo** umbral |
| `import_rates_from_excel.py:100, 113` | Ciudades, paquetes, proveedores y especiales: 95; alias de ciudad: 90 (l.199) |
| `import_companies_from_excel.py:262` | PAQUETE (opción 5): 95 |
| `cup_resolver.py:37` | Sugerencia F4 de CUP: 90 (nunca se aplica) |
| `src/odooInjection/domain/services/city_account_resolver.py:10` ✔ | Ciudad → cuenta analítica: WRatio ≥ 80; respaldo AA8638 |

### Numeración, fechas y agrupaciones
| Archivo:línea | Regla |
|---|---|
| — | El código no genera consecutivos. Los números de factura vienen del Excel externo (`# FACTURA`) y Odoo asigna el definitivo |
| `assigned_rates.py:48-81` | Las facturas se agrupan por `N° Identificación` (texto, MAYÚSCULAS, sin espacios) y se unen con ", "; esto también reescribe la columna de salida |
| `main.py:81-84` | El libro de facturas solo se pide si `día < DAY_INITIAL` o `día > DAY_FINAL` (bordes inclusivos dentro de la ventana) |
| `src/preInvoice/application/use_cases/split_by_nit.py:141-153` | GENERAL con alguna factura que empiece por "SET" → carpeta `GENERAL`; si no, → `General sin factura`; sin facturador → `SIN_FACTURADOR` |
| `assigned_rates.py:825` | Fecha límite = último día del mes anterior |
| `assigned_rates.py:31-35` | Aviso (solo en el log) si la fecha es > 90 días anterior al límite o posterior a él |
| `assigned_rates.py:858-898` | dd/mm/yyyy se conserva; yyyy-mm-dd → dd/mm/yyyy con intercambio día/mes condicionado al mes del límite; si el mes es > 12, intercambio sin condición; lo no interpretable queda en "" |
| `src/odooInjection/config.py:9-10`; `inject_invoices_to_odoo.py:189-207` | `invoice_date` = hoy, vencimiento = hoy + 30, `date_of_service` = fin del mes anterior, `range_id` según la Fecha Ingreso de la última fila |

### Normalización de datos de entrada
| Archivo:línea | Regla |
|---|---|
| `cup_resolver.py:67-132`; `cup_column_validator.py:61-76` | Corrección de CUP: F0 intercambio CUP↔VALOR, F1 nombre exacto del catálogo, F2 co-ocurrencia única, F3 sufijo `split("-")[0]`, F4 sugerencia (no se aplica); `VERIFIED=True` = el CUP sigue sin existir |
| `excel_provider_normalize_repository.py:14, 53-70, 119-121` | CONTRATO unificado por un slug que solo conserva `[A-Za-z]` (sin dígitos); gana el primero en orden descendente |
| `src/shared/utils/mega_dataframes.py:64-172` | CONTRATO: TARIFAS→TARIFA, PAQUETES→PAQUETE, strip, upper; se reparte entre hojas por prefijo o contenido |
| `import_rates_from_excel.py:207-209`; `assigned_rates.py:809-813` | INTRA O EXTRA / TIPO DE ACTIVIDAD vacío → "INTRA"; INTRAMURAL→INTRA, EXTRAMURAL→EXTRA |
| `assigned_rates.py:787-789`; `xmlrpc_odoo_repository.py:11` | Siglas: S A S→SAS, S A→SA, L T D A→LTDA, E U→EU, E S P→ESP; regex de sufijos para búsquedas por nombre en Odoo |

---

## Hallazgos

Tipos: bug · rendimiento · duplicación · legibilidad · seguridad · dependencias · manejo de errores · falta de pruebas.
Estados: pendiente · aprobado · descartado · después · hecho · revisar

### Severidad alta
| ID | Archivo:línea | Tipo | Severidad | ¿Toca lógica? | Propuesta | Estado |
|----|---------------|------|-----------|---------------|-----------|--------|
| AUD-01 ✔ | src/dataProcessing/infrastructure/persistence/cup_column_validator.py:33-35 | bug | alta | sí | Con separador de miles, VALOR se trunca: "150.000"→150, "1.234.567"→1, "1500.5"→15005, "150,000"→None. El docstring reconoce un bug, pero con un ejemplo distinto. **Caracterizar primero**, decidir el formato con negocio (P-03) y luego un parser único de montos | descartado (opción en desuso; decisión previa: aprobado) |
| AUD-02 ✔ | src/rates/application/use_cases/import_rates_from_excel.py:205 | bug | alta | sí | `replace_all(r"\D","")` multiplica ×10 los valores con decimales (150000.5 → 1500005) e interpreta distinto que la opción 3. Unificar con AUD-01 en un solo parser compartido | descartado (opción en desuso; decisión previa: aprobado) |
| AUD-03 ✔ | src/shared/utils/rapidfuzz_biller.py:18-29 | bug | alta | sí | `partial_ratio` con el mismo umbral acepta subcadenas ("ACME" = "ACME INDUSTRIAL S.A.S."). En la opción 1, Odoo por nombre corrige el NIT con un candidato equivocado; en la opción 4 renombra especiales (AUD-04). Umbral propio o longitud mínima, según P-08 | revisar |
| AUD-04 ✔ | src/rates/application/use_cases/import_rates_from_excel.py:113-117, 176-179 | bug | alta | sí | Un especial con similitud ≥ 95 **renombra** en BD el registro existente, sin hallazgo ni confirmación, y sus tarifas pasan al nombre nuevo. Registrar como hallazgo o pedir confirmación (P-06) | descartado (opción en desuso) |
| AUD-05 ✔ | src/rates/infrastructure/persistence/sa_rates_repository.py:90, 123 (usado en assigned_rates.py:1340, 1428, 1477) | bug | alta | sí | `find_any_rate`/`find_rate_by_cup_activity` toman la primera fila de una consulta **sin ORDER BY**: el precio de las fases 3, 5 y 6 no es determinista entre corridas, lo que impide un golden master estable. Definir el criterio (P-02) y añadir `order_by` | aprobado |
| AUD-06 | src/scrapping/infrastructure/scrapers/rues_selenium_scraper.py:148-149, 155-156 | manejo de errores | alta | sí | Un fallo técnico de RUES (timeout, bloqueo, caída del worker) se traga y el NIT queda como "No encontrado" en el libro persistente y en `data.json`. Devolver un estado de error distinto al de no encontrado | aprobado |
| AUD-07 ✔ | src/odooInjection/application/use_cases/inject_invoices_to_odoo.py:52-56; infrastructure/reporting/excel_log_generator.py:20-43, 88-91 | bug | alta | sí | El anti-duplicados excluye cualquier NIT que **alguna vez** quedó en OK en `odoo-output/log_inyeccion.xlsx` (histórico acumulado, sin periodo): desde el 2º mes no se facturaría a nadie ya facturado. Clave NIT+periodo o guarda en Odoo como en ETL (P-10) | después (integración ETL; decisión previa: aprobado) |
| AUD-08 ✔ | src/odooInjection/domain/services/city_account_resolver.py:27-35; domain/entities/city_account_map.py:1 | bug | alta | sí | Una ciudad desconocida o vacía cae en AA8638 (Bogotá), y además se acepta fuzzy ≥ 80. ETL eliminó ambas cosas porque imputaba a la sede equivocada (Pipeline.py:101-109). Portar la resolución de ETL | después (integración ETL; decisión previa: aprobado) |
| AUD-09 ✔ | src/odooInjection/domain/entities/city_account_map.py (AA10801 ×8, AA10010, AA10325); xmlrpc_odoo_repository.py:276-281 | bug | alta | sí | Hay códigos analíticos repetidos para ciudades distintas, y la búsqueda es por `code` con `limit=1`. ETL corrigió el mapa el 28-oct-2026 (BELLO→AA11096, LIBANO→AA11130…). Adoptar el mapa de ETL (P-15) | después (integración ETL; decisión previa: aprobado) |
| AUD-10 ✔ | src/odooInjection/application/use_cases/inject_invoices_to_odoo.py:133-134; xmlrpc_odoo_repository.py:219-228 | bug | alta | sí | Si no encuentra el NIT, factura al primer partner cuyo nombre contiene el texto (`ilike`, `limit 1`). ETL lo prohíbe porque "facturaba a terceros". Quitar el respaldo por nombre y devolver VERIFICAR | después (integración ETL; decisión previa: DESCARTAR) |
| AUD-11 | src/odooInjection/infrastructure/odoo/xmlrpc_odoo_repository.py:35, 39, 49-52 | manejo de errores | alta | no | `ServerProxy` sin timeout (puede colgarse indefinidamente) y sin guarda en Odoo antes de `create`: si Odoo crea la factura y la respuesta falla, la siguiente corrida la duplica. Timeout, reintento solo ante errores de red y búsqueda previa de `account.move` como en ETL (Pipeline.py:1259-1274) | hecho (solo timeout, ODOO_TIMEOUT_SECONDS=180; guarda de create queda para la integración ETL) |

### Severidad media
| ID | Archivo:línea | Tipo | Severidad | ¿Toca lógica? | Propuesta | Estado |
|----|---------------|------|-----------|---------------|-----------|--------|
| AUD-12 ✔ | src/scrapping/infrastructure/scrapers/rues_selenium_scraper.py:110-113 | bug | media | sí | La búsqueda por NIT acepta la **primera tarjeta** sin comprobar que su NIT coincida. Extraer el NIT y compararlo | revisar |
| AUD-13 | src/scrapping/application/use_cases/search_nits_with_odoo_fallback_use_case.py:151, 160-165 | bug | media | sí | `default_bases` se calcula antes del lote de Odoo; si Odoo falla, lo que resuelva RUES se marca "falta en Odoo" aunque no se consultó. Recalcularlo después del lote | revisar |
| AUD-14 | search_nits_with_odoo_fallback_use_case.py:197-198, 213-214; not_found_companies_log_generator.py:109-115 | bug | media | sí | Un NIT que solo existe en la BD local (con Odoo disponible) sale del libro de no encontrados. Depende de P-04 | revisar |
| AUD-15 | src/rates/application/use_cases/import_rates_from_excel.py:94-104, 141-162, 217 | bug | media | sí | Un contrato resuelto por fuzzy se guarda con el nombre del catálogo, pero las relaciones lo buscan por el nombre original: todas sus filas terminan en `contrato_no_existe`. Crear un mapa de alias igual que `city_alias` | descartado (opción en desuso; decisión previa: revisar) |
| AUD-16 | src/dataProcessing/infrastructure/persistence/excel_package_normalize_repository.py:52, 68, 71, 78-79, 89 (ídem en provider/special) | bug | media | sí | `str.replace` de Polars solo sustituye la **primera** coincidencia; en CUP/EXAMEN el reemplazo es "", así que se unen palabras ("RX  TORAX" → "RXTORAX"). Caracterizar antes de cambiar | descartado (opción en desuso; decisión previa: revisar) |
| AUD-17 | excel_provider_normalize_repository.py:14, 59, 119-121 (ídem special) | bug | media | sí | El slug elimina los dígitos: "CONTRATO 2024" y "CONTRATO 2025" se fusionan. Depende de P-05 | descartado (opción en desuso; decisión previa: revisar) |
| AUD-18 ✔ | src/assign/application/use_cases/assigned_rates.py:1242-1244, 1305-1306 | bug | media | sí | Sin `city_id` o `activity_id`, la fila salta **todas** las fases locales, incluida la 6, que no usa la ciudad. Depende de P-07 | revisar |
| AUD-19 ✔ | src/odooInjection/infrastructure/persistence/excel_pre_invoice_reader.py:61 | bug | media | sí | `rstrip(".0")` quita caracteres, no el sufijo: "903810.0" → "90381". Usar `removesuffix(".0")` como ETL | después (integración ETL; decisión previa: revisar) |
| AUD-20 | excel_pre_invoice_reader.py:12, 60, 69 | bug | media | sí | Solo se leen las primeras 14 columnas, por posición (la plantilla tiene 23); si NIT/Ciudad/Fecha Ingreso quedan fuera, la fila se descarta en silencio. Leer por nombre y validar las columnas requeridas | después (integración ETL; decisión previa: revisar) |
| AUD-21 | inject_invoices_to_odoo.py:114; xmlrpc_odoo_repository.py:113-116 | bug | media | sí | El NIT del Excel no se normaliza: un NIT con DV o puntos nunca coincide y cae en el respaldo por nombre (AUD-10) | después (integración ETL; decisión previa: revisar) |
| AUD-22 | xmlrpc_odoo_repository.py:115-117 | bug | media | sí | Si varios partners tienen el mismo NIT, gana el de menor id sin aviso; ETL lo manda a VERIFICAR (P-11) | después (integración ETL; decisión previa: descartar) |
| AUD-23 | inject_invoices_to_odoo.py:121, 205; xmlrpc_odoo_repository.py:330-334 | bug | media | sí | `range_id` sale de la Fecha Ingreso de la **última** fila; si el formato no es AAAA-MM-DD, toma en silencio el rango más reciente (P-12) | después (integración ETL; decisión previa: aprobar) |
| AUD-24 | xmlrpc_odoo_repository.py:293-302 | bug | media | sí | El respaldo del impuesto por `ilike` de 20 caracteres puede aplicar otro impuesto. Es paridad con ETL: no tocar sin P-13 | después (integración ETL; decisión previa: descartar) |
| AUD-25 | xmlrpc_odoo_repository.py:260-271; domain/repositories/odoo_connection_repository.py:58-60 | seguridad | media | sí | `create_client` (`res.partner create`) existe y nadie lo llama; contradice ADR-010. Eliminarlo del puerto, del adaptador y del fake | aprobado |
| AUD-26 | src/billers/application/use_cases/import_billers_from_excel.py:89-91 | bug | media | sí | La opción 2 trunca cédulas de 10 dígitos; la opción 5 las conserva: la misma persona puede quedar con dos registros en `companies` (P-09) | aprobado |
| AUD-27 | import_billers_from_excel.py:116-138; sa_company_repository.py:79 | bug | media | sí | La opción 2 inserta empresas **no verificadas** con `verified_at=now()` (P-16) | aprobado |
| AUD-28 | text_normalizer.py:48-53; assigned_rates.py:427-445, 522-530; import_billers_from_excel.py:89-91; sa_company_repository.py:60-66 | duplicación | media | sí | La normalización de NIT está reimplementada en 4 sitios y la de nombre de empresa con criterios distintos. Centralizar en `text_normalizer` con pruebas de paridad | descartar |
| AUD-29 | main.py:44-46; import_information_controller.py:31; import_rates_controller.py:51; import_companies_rates_controller.py:84 | dependencias | media | sí | Las opciones 3, 4 y 5 están @deprecated, pero la 4 es el **único** escritor de `rates/packages/providers/specials/cities`, que la opción 6 usa como respaldo. No retirar sin P-01 | aprobado |
| AUD-30 | main.py:82-84 | manejo de errores | media | no | `int(getenv("DAY_INITIAL"))` lanza un error si falta o está vacía (como en `.env.example`), y el usuario ve un error genérico. Leerla vía `config.py` con un mensaje claro, sin cambiar la condición | descartado |
| AUD-31 | src/preInvoice/application/use_cases/split_by_nit.py:214-218, 276-279; pre_invoice_controller.py:32-35 | manejo de errores | media | no | Los errores por NIT se tragan y aun así se muestra "Pre-facturas generadas exitosamente". Contar los fallos y mostrar un resumen (ADR-014) | hecho (aviso con conteos solo si falla algún NIT) |
| AUD-32 | sa_rates_repository.py:61, 92, 125 + assigned_rates_controller.py:121 | manejo de errores | media | no | Si falla la consulta de tarifas se devuelve `{}` y el aviso queda oculto por `TechOnlyLogger`: parece "sin resolver", no un error. Propagar el fallo o marcarlo en el resultado | hecho (variante i: aviso en el resumen solo si falla + rollback) |
| AUD-33 | assigned_rates.py:1069-1073 | rendimiento | media | no | `provider_repo.all()` y `special_repo.all()` dentro del bucle por empresa (una consulta por empresa). Construir mapas una sola vez | hecho (3.000 empresas, 5 ms/consulta: 1.800 consultas, 9,5 s → 2 consultas, 19 ms; salida idéntica) |
| AUD-34 | assigned_rates.py:563-633 | rendimiento | media | no | Hasta 3 llamadas XML-RPC en serie por NIT o nombre único. Buscar en lote (`ref_num in [...]`) | hecho (solo rama por NIT; los NIT ambiguos —fila llegada por la condición de otro NIT o más de un partner— se resuelven con la consulta individual; 1.000 NIT con 233 duplicados, 20 ms/llamada: 2.599 llamadas XML-RPC, 57 s → 259 llamadas, 8 s; salida idéntica) |
| AUD-35 | search_nits_with_odoo_fallback_use_case.py:176-181 | rendimiento | media | no | Una llamada `find_clients_by_name` por cada nombre pendiente, sin tope. Poner un tope o una consulta agrupada | revisar (tope o consulta agrupada cambian resultados; paralelizar = concurrencia. Decidir con la integración ETL) |
| AUD-36 | inject_invoices_to_odoo.py:131; xmlrpc_odoo_repository.py:65-67 | rendimiento | media | no | N+1 sobre `res.partner` (hasta 5 llamadas por empresa) cuando ya existe `find_clients_batch` | después (integración ETL; decisión previa: aprobado) |
| AUD-37 | excel_package_normalize_repository.py:41-46; excel_provider/special_normalize_repository.py:45-50 | manejo de errores | media | no | `except Exception` devuelve None y luego hay `AttributeError` en el exportador; un libro sin hojas TarifasEspeciales tumba la opción 3. Devolver un DataFrame vacío y registrar un hallazgo | descartado (opción en desuso; decisión previa: aprobar) |
| AUD-38 | import_rates_from_excel.py:214-288 | manejo de errores | media | no | Un único `try` envuelve todo el bucle: un nulo en CONTRATO/CIUDAD/CUP aborta el resto de filas, con commit parcial. Validar nulos por fila | descartado (opción en desuso; decisión previa: aprobar) |
| AUD-39 | sa_rates_repository.py:145-148; sa_package/provider/special/city repos | manejo de errores | media | no | `save_batch` traga los errores y devuelve `[]`/0; el resumen no refleja lo que no se guardó; `all()` devuelve None y rompe la línea 189 | descartado (opción en desuso; decisión previa: revisar) |
| AUD-40 | src/company/application/use_cases/import_companies_from_excel.py:171-175, 329-332 | manejo de errores | media | no | Los contadores del resumen se asignan aunque `save_batch` falle: el usuario puede ver éxitos falsos. Contar sobre el valor devuelto | descartado (opción en desuso; decisión previa: aprobar) |
| AUD-41 | import_billers_from_excel.py:142-146 | manejo de errores | media | no | `all()` puede devolver None y se itera sin protección; además se llama dos veces seguidas (2 barridos de `companies`) | hecho (una sola lectura; el TypeError ante None se conserva: or [] silenciaría un fallo de BD) |
| AUD-42 | src/billers/infrastructure/persistence/sa_biller_repository.py:18-20, 54-56; sa_biller_company_repository.py:41-43 | manejo de errores | media | no | Capturan la excepción sin `session.rollback()`: la sesión queda inutilizable (PendingRollbackError). Agregar rollback | hecho |
| AUD-43 | assigned_rates_controller.py:122; import_billers_controller.py:70-72; detect_duplicates_controller.py:21; import_rues_nits.py:86; import_information_controller.py:38; import_rates_controller.py:56 | manejo de errores | media | no | `get_session()` sin cerrar (las opciones 5 y 7 sí la cierran). Usar `with get_session() as session` | hecho (opciones 1, 2, 6, 10; 3 y 4 en desuso) |
| AUD-44 | src/shared/database/models.py vs migrations/versions/* | dependencias | media | no | `models.py` no coincide con el esquema real: le falta `deleted_at` en 11 modelos, las FK de `rates` y `companies_billers` y el RBAC. `alembic --autogenerate` propondría borrados. Alinear o prohibir autogenerate | hecho (variante b: sin tocar models.py; prueba de vigilancia + autogenerate prohibido) |
| AUD-45 | migrations/env.py:16-24 vs src/shared/database/database.py:13-21; .env.example | seguridad | media | no | Alembic acepta `DATABASE_URL` y la app no (pueden apuntar a BD distintas); env.py usa el puerto 6543 sin `sslmode`, la app 5432 con `require`; el usuario no va con `quote_plus` y no hay `connect_timeout`. Una sola función de URL | hecho (variante b: DATABASE_URL o SUPABASE_* con 5432 y sslmode=require para app y Alembic) |
| AUD-46 | requirements.txt | dependencias | media | no | Sin ningún import: supabase y sus 5 paquetes, mysql-connector + PyMySQL, psycopg v3, selenium y sus transitivas, requests, xlsx2csv, pyiceberg, pydantic; además los envoltorios `dotenv`/`bs4` y pytest mezclado con runtime. Crear `requirements.in` mínimo + `requirements-dev`, validado en un venv limpio | hecho (89 → 25 paquetes + requirements-dev.txt; verificado en venv limpio) |
| AUD-47 | excel_package/provider/special_normalize_repository.py; mega_dataframes.py:64-162; sa_package/provider/special/city_repository.py | duplicación | media | no | 3 normalizadores casi idénticos, el bloque de CONTRATO repetido 7 veces y el CRUD repetido en 4 repos. Clase base o función paramétrica | revisar |
| AUD-48 | assigned_rates.py:822-898 | falta de pruebas | media | sí | No hay pruebas de `_parse_fecha`/`_normalize_fecha` (intercambio día/mes, límite, formato sin ceros). Caracterizar antes de tocar | revisar |
| AUD-49 | assigned_rates.py:1531-1536; tests/rates/test_total_column.py:7-9 | falta de pruebas | media | sí | La prueba de Total verifica una **copia** de la fórmula, no el use case | aprobar |
| AUD-50 | main.py:79-85 | falta de pruebas | media | sí | La ventana DAY_INITIAL/DAY_FINAL y sus bordes no tienen pruebas | descartar |
| AUD-51 | src/odooInjection (reader, controller, config, XmlRpc connect/find_tax/find_uom/find_date_range/create_invoice) | falta de pruebas | media | no | Sin pruebas; `test_inject_invoices.py` no comprueba tax_ids, cuentas, fechas ni range_id. Necesario antes de la paridad con ETL | aprobar |
| AUD-52 | cup_column_validator.py; import_rates_from_excel.py:_resolve_names*; rapidfuzz_biller; rues scraper; search_nits use case | falta de pruebas | media | sí | Faltan casos para: VALOR con miles y decimales, fuzzy/renombrado real, `partial_ratio`, fallo de un worker de RUES, `default_bases` tras fallar Odoo y celdas `nits` vacías | descartar |
| AUD-53 | assigned_rates.py:825 | falta de pruebas | media | no | `_normalize_fecha` usa `date.today()` en vez del reloj inyectado `self._today`, así que el resultado depende del día. Usar `self._today()` | descartar |

### Severidad baja
| ID | Archivo:línea | Tipo | Severidad | ¿Toca lógica? | Propuesta | Estado |
|----|---------------|------|-----------|---------------|-----------|--------|
| AUD-54 | tests/test_main_menu.py:22-40; tests/docs/test_user_audit_docs.py:43-64 | falta de pruebas | baja | no | 4 fallas de base. (a) La opción 9 se deprecó a propósito (a196be6, 2026-10-21) después de la prueba (52ddf9c): la prueba está desactualizada, y USER_GUIDE.md:97, 344, 395 y 440 aún recomienda la opción 9. (b) Las pruebas de docs exigen `.claude/rules/*.md`, que están ignorados por git. Actualizar según P-01 | hecho |
| AUD-55 | src/preInvoice/infrastructure/console/pre_invoice_controller.py:19-21 | legibilidad | baja | no | `print()` con marcado Rich (sale literal) y duplica el `user_msg` | hecho (se conserva el mensaje; solo deja de verse [red] literal) |
| AUD-56 ✔ | split_by_nit.py:50, 54 | legibilidad | baja | sí (Leyenda) | La Leyenda muestra una "Fase 7" que ya no existe; `_PHASE_COLORS_ARGB` no se usa; los colores están duplicados con assigned_rates.py:94-103 (P-17) | revisar |
| AUD-57 | assigned_rates.py:1480 | legibilidad | baja | no | `if 'pkg_id_to_name' not in dir()`: frágil. Inicializar los mapas antes de la fase 3 | hecho |
| AUD-58 | assigned_rates.py:1185, 1263, 1272, 1336, 1377, 1415, 1474 | legibilidad | baja | no | Los comentarios dicen "Phase 1..7" y las claves fase_01..06 (la "Phase 7" del código es fase_06) | hecho |
| AUD-59 | assigned_rates.py:1179; split_by_nit.py:12; excel_pre_invoice_reader.py:11; Pipeline.py:197 | bug | baja | sí | Tres reglas distintas para reconocer columnas CUP (`isdigit` sin guiones, `^\d+(-\d+)?$`, `^\d{6}(-\d{1,2})?$`). Un solo predicado | revisar |
| AUD-60 | assigned_rates.py:1183 | manejo de errores | baja | no | `cast(pl.Int64)` estricto: un texto en una celda CUP aborta la opción 6. Validar y reportar la fila y la columna | hecho (variante a: detalle en log técnico; el usuario sigue viendo el mensaje genérico) |
| AUD-61 | src/assign/application/use_cases/missing_rates.py:23, 44 | bug | baja | sí | `== "1"` no detecta "1.0"; `pl.concat` en bucle; PAQUETE ya no es el paquete local. Solo si la opción 9 sigue viva | descartado (opción en desuso; decisión previa: revisar) |
| AUD-62 | assigned_rates.py:268; pre_invoice_controller.py:8 | legibilidad | baja | no | La ruta de `CONSOLIDADO.xlsx` está escrita a mano en 2 módulos y se sobrescribe sin confirmar. Llevarla a `config.py` con el mismo valor | hecho (sin confirmación de sobrescritura: cambiaría comportamiento) |
| AUD-63 | src/odooInjection/config.py:28 | bug | baja | sí | `.split(",")` sin strip: "100006, 100007" deja " 100007" sin gravar | después (integración ETL; decisión previa: revisar) |
| AUD-64 | odooInjection/config.py:6; database.py:10; logging_config.py:13; main.py:38; migrations/env.py:12 | legibilidad | baja | no | `load_dotenv` en 5 sitios, como efecto al importar y con precedencias distintas | hecho (app: carga única; migrations/env.py sin cambios → AUD-45) |
| AUD-65 | invoice_line.py; sa_company_repository.py:103-126; sa_biller_company_repository.py:13-22; company_name_normalizer.py; nit_service.py:51-60; search_nits_use_case.py:19-20 | legibilidad | baja | no | Código muerto (verificado con grep: solo lo usan las pruebas o nadie). Eliminar junto con sus pruebas | hecho (sin invoice_line.py, opción 8) |
| AUD-66 | rapidfuzz_biller.py:24-34 | manejo de errores | baja | no | Con un catálogo vacío lanza TypeError que se captura y registra `user_msg` en **cada fila** | hecho (mismo mensaje, una vez por ejecución) |
| AUD-67 | rues_selenium_scraper.py:59-62; sa_company_repository.py:69-72 | legibilidad | baja | sí (mensajes) | `user_msg` por fila, contra ADR-014. Cambiarlo altera los mensajes: consultar | revisar |
| AUD-68 | import_rues_nits.py:91-108; rues_selenium_scraper.py:37-42 | manejo de errores | baja | no | `int(os.getenv(...))` y `os.path.join(os.getenv("BOOK_ROUTE"))` sin validar. Leer vía `config.py` | hecho (mensaje nuevo solo si falta BOOK_ROUTE/BOOK_NAME) |
| AUD-69 | rues_selenium_scraper.py:4, 54, 76-92, 23-24 | dependencias | baja | no | numpy solo para `isnan`; el archivo se llama "selenium" pero usa Playwright; timeouts fijos; XPath absolutos | hecho (solo numpy; renombre del archivo, timeouts y XPath pendientes) |
| AUD-70 | sa_package_repository.py:55; sa_provider_repository.py:55; sa_special_repository.py:54 | dependencias | baja | no | `session.query(M).get(id)` es API legacy de SQLAlchemy 2.0; usar `session.get(M, id)` | revisar |
| AUD-71 | not_found_companies_log_generator.py:133, 143 | bug | baja | sí | El histórico se indexa por el NIT crudo, no normalizado: duplica filas con DV o puntos | aprobado |
| AUD-72 | import_rues_nits.py:114; search_nits use case:132 | bug | baja | no | Una celda vacía en `nits` aparece como NIT "None" no encontrado. Filtrar nulos | descartar |
| AUD-73 | import_rates_from_excel.py:99, 112, 185-187; import_information_controller.py:42-44 | rendimiento | baja | no | Pertenencia sobre listas O(n·m); los catálogos se consultan 3 veces | revisar |
| AUD-74 | excel_provider/special_normalize_repository.py:62-65; cup_column_validator.py:191; assigned_rates.py:1572-1578; import_companies_from_excel.py:244-265 | rendimiento | baja | no | `map_elements` fila a fila; aplicarlo sobre `unique()` y luego unir | hecho (solo opción 6; _validate_empresa 260.000 filas: mediana 2.65–3.12 s → 0.32–0.36 s, salida idéntica) |
| AUD-75 | split_by_nit.py:172-175, 220-223, 236-239, 283-284; 178-210 vs 244-273 | legibilidad | baja | no | `__enter__`/`__exit__` manuales y el mismo cálculo repetido por NIT en los dos procesos | hecho |
| AUD-76 | split_by_nit.py:263-269 | bug | baja | no | Desduplicar nombres de hoja puede chocar con otra empresa (Excel no distingue mayúsculas) | hecho (solo cambia el nombre de hoja cuando hay choque) |
| AUD-77 | migrations/versions/6f0ab654aacd_*.py:4; bc1d152a1ddb_*.py:4 | legibilidad | baja | no | El docstring "Revises:" no coincide con `down_revision` (la cadena real es correcta) | hecho |
| AUD-78 | src/shared/console/sheet_input.py:10; import_billers_from_excel.py:1-3, 28; import_companies_from_excel.py:1, 29 | legibilidad | baja | no | `print()` sin Rich, imports sin uso, herencia de un "repositorio" ABC innecesaria | hecho (sin import_companies, opción 5) |
| AUD-79 | src/shared/database/database.py:2, 24 | legibilidad | baja | no | `import urllib` sin `urllib.parse`; el engine se crea al importar (cualquier import de modelos arma la URL) | hecho (solo el import; el engine diferido queda pendiente como estructura) |

### Hallazgos de la caracterización (golden master, 2026-11-05)
Se detectaron al construir `tests/golden/` y se verificaron ejecutando el sistema con distintos `PYTHONHASHSEED`.
| ID | Archivo:línea | Tipo | Severidad | ¿Toca lógica? | Propuesta | Estado |
|----|---------------|------|-----------|---------------|-----------|--------|
| AUD-80 ✔ | src/dataProcessing/infrastructure/persistence/cup_column_validator.py:99-103, 122-128 | bug | baja | no | El orden de las filas de `logs/novedades_cups.xlsx` y de "Contratos (ejemplos)" cambia entre ejecuciones con los mismos datos (`group_by` sin `maintain_order`, `unique()`). Agregar `maintain_order=True` / `unique(maintain_order=True)`. El golden lo normaliza (N6) | pendiente |
| AUD-81 ✔ | src/assign/application/use_cases/assigned_rates.py:57-71 | bug | baja | sí (formato de salida) | La columna FACTURAS lista los mismos números en orden distinto entre ejecuciones ("SET100, FAC200" / "FAC200, SET100"), y esto llega al CONSOLIDADO y a las pre-facturas. No cambia la clasificación SET (es por "alguna"). Definir el orden (P-29) y usar `maintain_order` | pendiente |
| AUD-82 ✔ | src/rates/application/use_cases/import_rates_from_excel.py:98 (desde `_progress_city`, l.129) | manejo de errores | media | no | Una sola celda CIUDAD vacía en el tarifario lanza `AttributeError: 'NoneType' object has no attribute 'upper'` y aborta toda la opción 4 antes de guardar nada, sin mensaje al usuario (solo el genérico de `safe_dispatch`). Validar nulos y reportarlos como hallazgo | descartado (opción en desuso; decisión previa: pendiente) |

### Comparación con ETL-Avancys (insumo para la integración)
`src/odooInjection` es una **versión anterior** de `Pipeline.py`, sin las correcciones de octubre de 2026. Comparten la lectura (fila 2 = encabezados, se excluyen "~$" y "consolidado"), el conteo por (examen, cuenta), `price_unit=list_price`, la cuenta gravada para 100006, las dos autorretenciones, la UoM "Unidades", `out_invoice` draft en el diario 47 y la regla VERIFICAR.

| Aspecto | ETL (producción) | Opción 8 |
|---|---|---|
| Columnas | Por nombre, validando las requeridas | Las primeras 14 por posición (AUD-20) |
| Códigos de examen | `^\d{6}(-\d{1,2})?$`, `removesuffix` | `^\d+(-\d+)?$`, `rstrip` (AUD-19) |
| Cuenta analítica | Por sede/extramural/id, desempate por nombre, sin fuzzy ni respaldo; si no resuelve, los exámenes quedan pendientes | Mapa desactualizado, fuzzy ≥ 80, respaldo Bogotá (AUD-08/09) |
| Cliente | Solo `ref_num` exacto; varios partners → VERIFICAR; nunca por nombre | 4 etapas con `=like`, menor id, respaldo por nombre (AUD-10/22) |
| Bloqueos | NITS_BLOQUEADOS, EMPRESAS_BLOQUEADAS, YA_SUBIDAS | No existen |
| Calidad | Aviso de cobro doble, cuadre archivo = facturado + apartado, chequeo de periodo por "Base" | No existen |
| Fechas | No envía fechas; limpia el vencimiento tras crear | Envía 4 fechas (AUD-23) |
| Anti-duplicados | `search_read` de `account.move` draft antes de crear; reintento con reconexión | Log local sin periodo (AUD-07/11) |
| Salidas | log xlsx+txt, facturas_creadas.csv, pendientes_facturador.xlsx, cuentas_por_revisar.xlsx; guardado cada 10 empresas | Solo log_inyeccion.xlsx al final |
| Orden de líneas | Ordenadas por clave | Orden de inserción |
| Variable de usuario | `ODOO_USER` | `ODOO_USERNAME` |

---

## No se toca

| Elemento | Dónde | Por qué |
|---|---|---|
| Contrato de la pre-factura | split_by_nit.py:14-38, 203-210, 417-492 | Lo consume ETL (Pipeline.py:873-912): "BASE GENERAL" como **primera** hoja; fila 1 = nombres CUPS, fila 2 = encabezados, datos desde la fila 3; nombres exactos NIT/Empresa/Ciudad/Sede/Paciente/N° Identificación/Ingreso N°; nombres de archivo `pre_factura_<NIT>_<Empresa>.xlsx` y `NITs_consolidado.xlsx` (ETL excluye "consolidado") |
| Contrato de CONSOLIDADO.xlsx | assigned_rates.py:266-345, 303-327 | Nombre, ubicación, hoja "Consolidado", 23 columnas fijas y colores ARGB por fase: la opción 7 los lee por valor exacto |
| Valor 1 en celdas sin resolver y su suma en Total | assigned_rates.py:1517, 1531-1536 | Comportamiento documentado (phase_findings_reporter.py:27); lo usan la lectura humana y la opción 9 |
| Truncamiento `int()` de precios, cascada F1-F6, "PAQUETE C 2025" | odoo_rate_index.py:47; assigned_rates.py:1312-1517 | Reglas de negocio vigentes; cualquier cambio altera los montos |
| Parseo de VALOR (opciones 3 y 4) | cup_column_validator.py:24-42; import_rates_from_excel.py:203-205 | Aunque haya bugs (AUD-01/02), corregirlo cambia las tarifas cargadas. Primero caracterizar y decidir |
| `normalize_nit` a 9 dígitos y `document_normalizer` | text_normalizer.py:48-53; document_normalizer.py | Odoo empareja `ref_num` de 9 dígitos; `companies.nit` ya está guardado así |
| Cascada Odoo → BD → RUES y no escribir en Odoo salvo el borrador | ADR-013, ADR-010 | Decisiones arquitectónicas aceptadas |
| Anti-duplicados previos al INSERT y clave de conflicto de `rates` | sa_rates_repository.py:139; ADR-009/012 | Integridad de datos |
| Corrección de CUP F0-F4 (F4 nunca se aplica) y exclusión de colisiones | cup_resolver.py | RF-05; define qué CUP se factura |
| Umbrales fuzzy (80, 85, 90, 95) y unificación por slug | ver Reglas | Cambiarlos altera qué empresa, contrato o CUP se asigna; están medidos sobre datos reales |
| Configuración contable de la inyección | odooInjection/config.py:19-37 | Diario, cuentas, producto gravado e impuestos acordados; coinciden con ETL |
| Forma de la factura: `out_invoice`, draft, `(0,0,vals)`/`(6,0,ids)`, cantidad = conteo | inject_invoices_to_odoo.py:166-207 | Base de la paridad con ETL |
| Formato de fechas dd/mm/yyyy, ", " en FACTURAS, prefijo "SET", sufijo "(TIAN)" sin espacio, reescritura de `N° Identificación` | assigned_rates.py:54-71, 858-898, 958; split_by_nit.py:148-153 | Formatos de salida que afectan la clasificación por carpetas y las pre-facturas |
| Vocabulario de `checked_bases` y textos de Estado | nit_result.py:8-10; not_found_companies_log_generator.py:16-19 | El generador compara por igualdad exacta |
| Nombres, columnas y rutas de los libros de hallazgos y logs | logs/… (ADR-014) | El área operativa los consume |
| Textos de `user_msg` | todo `src/` | Regla 2 de CLAUDE.md (mensajes al usuario) |
| Migraciones ya aplicadas | migrations/versions/ | Están en la BD de producción; no se reescriben |
| Escrituras en la tabla `imedical` | assigned_rates.py:763-772 | Efecto de negocio (auto-registro) |
| Etiquetas @deprecated de las opciones 3, 4 y 5 | main.py; controllers | Las vigila tests/test_main_menu.py |

---

## Preguntas abiertas

| ID | Pregunta | Relacionado |
|---|---|---|
| P-01 | Si las opciones 3, 4, 5 y 9 están en desuso, ¿cómo se alimentan hoy las tablas `rates/packages/providers/specials/cities`? al estar en desuso se recibe de un externo y se deja en la carpeta fuentes ¿La cascada local es solo un respaldo que se puede congelar, o se sigue cargando cada tarifario nuevo? puedes cargar tarifario nuevo ¿La opción 9 está oficialmente retirada (la guía de usuario aún la recomienda)? si la 9 ya no se usa| AUD-29, AUD-54, AUD-61 |
| P-02 | En las fases 3, 5 y 6, cuando varias fuentes tienen tarifa para la misma clave, ¿cuál gana: el menor precio, un paquete preferido o el registro más reciente? el mas reciente| AUD-05 |
| P-03 | ¿Cuál es el formato real de VALOR en los tarifarios ("150.000", "150000", "150,000", con decimales)?sin decimales  Ante decimales, ¿se trunca o se redondea? ¿Deben coincidir las opciones 3 y 4? | AUD-01, AUD-02 |
| P-04 | ¿Un NIT que existe en la BD local pero **no** en Odoo (con Odoo disponible) debe aparecer como "falta en Odoo" en `empresas_no_encontradas.xlsx`? si| AUD-14 |
| P-05 | ¿Los contratos que solo difieren en números (años, sedes) deben fusionarse? no se ¿Por qué gana el mayor en orden descendente? no se| AUD-17 |
| P-06 | ¿El renombrado automático de especiales por similitud (incluida una subcadena) debe seguir así, o reportarse para revisión? debe seguir asi | AUD-03, AUD-04 |
| P-07 | Si la ciudad o la actividad de la fila no existen en la BD, ¿debe intentarse igual la fase 6 (cualquier ciudad)? si | AUD-18 |
| P-08 | ¿Se acepta que una razón social corta ("ACME") coincida con una más larga ("ACME INDUSTRIAL SAS") y se reemplace el NIT? no| AUD-03 |
| P-09 | ¿Se debe truncar a 9 dígitos una cédula de 10 en las opciones 1, 2 y 6? (La opción 5 la conserva.) si | AUD-26, AUD-28 |
| P-10 | Anti-duplicados de la inyección: ¿por lote o por periodo? lote ¿Cuál es la clave correcta: NIT+mes, la columna "Base", la guarda en Odoo como ETL? si | AUD-07, AUD-11 |
| P-11 | Si un NIT corresponde a varios partners en Odoo, ¿VERIFICAR o el de menor id? VERIFICAR| AUD-22 |
| P-12 | Fechas de la factura: ¿`invoice_date`=hoy, vencimiento +30, `date_of_service` y `range_id` (Facturacion), o sin fechas y con el vencimiento limpiado (ETL)? sin fechas | AUD-23 |
| P-13 | ¿Las dos autorretenciones van en todas las líneas, incluidos los productos excluidos? si ¿Se acepta el respaldo por `ilike` del nombre del impuesto? si | AUD-24 |
| P-14 | ¿Quién mueve las pre-facturas de `pre-facturas/<facturador>/` a la entrada del inyector, y qué carpetas se inyectan (solo GENERAL, "General sin factura", todas)? La opción 8 lee "General sin factura": ¿es correcto? nop la opcion 8 esta mal esa tambien esta en desuso esa es la que vamos a reemplazar por el etl que integraremos | Flujo, AUD-20 |
| P-15 | Mapa ciudad→cuenta analítica: ¿se adopta el de ETL (con SEDE_CUENTA y CIUDAD_CUENTA_ID) como fuente única? ¿Dónde debe vivir: código, BD u Odoo? en los 3 | AUD-08, AUD-09 |
| P-16 | ¿La opción 2 debe guardar en `companies` las empresas no verificadas? si ¿Con o sin `verified_at`? con | AUD-27 |
| P-17 | ¿Se puede quitar "Fase 7" de la Leyenda de las pre-facturas, o alguien la consume? no se debe quirar| AUD-56 |
| P-18 | ¿Celdas con valor distinto de 1 (2, 0.5, texto) deben sumar tal cual en Total? no ¿Es correcto que el 1 sin resolver sume? no | Reglas de totales |
| P-19 | ¿Los precios de Odoo con decimales se truncan (como hoy) o se redondean? se redondean| odoo_rate_index.py:47 |
| P-20 | ¿"PAQUETE C 2025" sigue vigente en 2026 o debe ser configurable? si esta vigente| assigned_rates.py:1060 |
| P-21 | Ventana DAY_INITIAL–DAY_FINAL: ¿los bordes son inclusivos a propósito? si ¿Qué valores se usan en producción? 5 y 29 Dentro de la ventana todo GENERAL termina en "General sin factura": ¿es lo esperado? si | main.py:81-84 |
| P-22 | Un NIT con unas filas con factura SET y otras sin ella genera dos pre-facturas en dos carpetas: ¿es correcto? no deberia ¿Las facturas que no empiezan por "SET" cuentan como "con factura"? no | split_by_nit.py:141-156 |
| P-23 | ¿El nombre "<empresa>(TIAN)" es el formato que espera Odoo/Avancys? es para poder hacer una referencia a que empresas deben ser facturadas a nombre de ese nit | assigned_rates.py:958 |
| P-24 | ¿Las fechas fuera de la ventana de 3 meses deben excluirse o marcarse en un libro, en vez de solo registrarse en el log? no  | assigned_rates.py:31-35 |
| P-25 | ¿Las opciones 2 y 5 deben buscar también por nombre (como la opción 1)? no deben buscar, Hoy no usan `name_matcher` | nit_service.py:23-28 |
| P-26 | ¿Se mantienen NITS_BLOQUEADOS, EMPRESAS_BLOQUEADAS, YA_SUBIDAS, `pendientes_facturador.xlsx` y el cuadre de ETL en la integración? si ¿Dónde se configuran? en unos archivo que yo subo| Comparación ETL |
| P-27 | ¿El "INTRA" por defecto cuando falta la actividad es correcto para todos los contratos? si| import_rates_from_excel.py:207-209 |
| P-28 | ¿La opción 1 debe reutilizar `data.json` como caché de RUES, como las opciones 2 y 5? si| AUD-06 |
| P-29 | ¿En qué orden deben listarse los números en la columna FACTURAS (orden del libro de facturas, alfabético, SET primero)? Hoy es arbitrario | AUD-81 |
