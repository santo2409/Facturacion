"""Carga de pre-facturas en Odoo: una factura borrador por empresa (opción 5).

Port de ETL-Avancys `Pipeline.py` (commit 7bb6784): `crear_factura_odoo` (1011-1298) y el
bloque principal (1672-1912), con el mismo orden de pasos, las mismas consultas y escrituras
a Odoo, los mismos estados y textos de detalle, y los mismos libros. Diferencias deliberadas:
  - la configuración mensual llega en `InjectionSettings` (Excel) en vez de constantes;
  - el log técnico va a `logs.log` (LoggerAdapter) y la consola muestra un único resumen;
  - las salidas van a una carpeta por corrida (InjectionReportWriter).
Los comportamientos dudosos del ETL se conservan para la paridad (E-09).
"""

import time
import xmlrpc.client
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from src.odooInjection.domain.entities.etl_constants import COLS_FIJAS, NUM_COLS_FIJAS
from src.odooInjection.domain.services.analytic_account_resolver import (
    AnalyticAccountResolver,
)
from src.odooInjection.domain.services.city_key import clave_ciudad, normalizar
from src.odooInjection.domain.services.nit_rules import limpiar_nit, nit_valido
from src.odooInjection.domain.services.pending_registry import PendingRegistry


class LoadPreInvoicesToOdoo:
    def __init__(self, gateway, source, settings, writer, logger, config: dict,
                 progress=None, sleep=time.sleep, now=datetime.now):
        self._gateway = gateway
        self._source = source
        self._settings = settings
        self._writer = writer
        self._log = logger
        self._config = config
        self._progress = progress
        self._sleep = sleep
        self._now = now
        self._resolver = AnalyticAccountResolver(gateway, logger)
        self._registry = PendingRegistry()

    @property
    def registry(self) -> PendingRegistry:
        return self._registry

    def url_factura(self, factura_id):
        return self._config["url"] + "/web#id=" + str(factura_id) + "&model=account.move&view_type=form"

    # ── Odoo ─────────────────────────────────────────────────────────────────
    def _buscar_cliente(self, nit, nombre):
        """Solo por NIT exacto contra res.partner.ref_num; nunca por nombre (Pipeline.py:835-864)."""
        if not nit_valido(nit):
            return None, None, None
        nit_limpio = nit.replace("-", "").replace(".", "").strip()
        r = self._gateway.find_partners_by_ref_num(list({nit, nit_limpio}))
        if not r:
            return None, None, None
        if len(r) > 1:
            self._log.warning("  NIT " + nit + " coincide con varios terceros: " +
                              str([(x["id"], x["name"]) for x in r]))
            return None, None, None
        score = SequenceMatcher(None, nombre.upper().strip(),
                                r[0]["name"].upper().strip()).ratio()
        if score < 0.60:
            self._log.warning("  NIT " + nit + " coincide pero el nombre difiere (" +
                              str(round(score * 100)) + "%): Excel='" + nombre[:45] +
                              "' vs Odoo='" + r[0]["name"][:45] + "'")
        return r[0]["id"], "[" + str(r[0]["ref_num"]) + "] " + r[0]["name"], "NIT"

    def _buscar_tax_id(self, nombre_tax):
        tax_id = self._gateway.find_tax(nombre_tax)
        if not tax_id:
            self._log.warning("  IMPUESTO NO ENCONTRADO en Odoo: '{}'".format(nombre_tax))
        return tax_id

    def _buscar_uom_id(self, nombre_uom):
        uom_id = self._gateway.find_uom(nombre_uom)
        if not uom_id:
            self._log.warning("  UdM NO ENCONTRADA en Odoo: '{}'".format(nombre_uom))
        return uom_id

    def _limpiar_fecha_vencimiento(self, factura_id):
        try:
            self._gateway.clear_due_date(factura_id)
        except Exception as e:
            self._log.warning("  No se pudo dejar en blanco el vencimiento: " + str(e)[:120])

    def _actualizar_precios(self, factura_id):
        try:
            self._gateway.update_prices(factura_id)
        except RuntimeError as e:
            faltantes = " ".join(str(e).split())
            return False, faltantes[:300], 0.0
        except Exception as e:
            return False, "Fallo al actualizar precios: " + str(e)[:150], 0.0
        total = self._gateway.amount_total(factura_id)
        return True, "", (total[0]["amount_total"] if total else 0.0)

    # ── Agrupación (Pipeline.py:981-1006) ───────────────────────────────────
    def _agrupar_por_empresa(self, todas_las_filas, todas_cols_examenes):
        empresas = defaultdict(lambda: {"nombre": "", "nit": "", "pacientes": []})
        sin_nit = []
        for fila in todas_las_filas:
            nit = str(fila.get("NIT") or "").strip()
            nombre = str(fila.get("Empresa") or "").strip()
            if not nit or nit == "None":
                sin_nit.append(fila)
                continue
            empresas[nit]["nombre"] = nombre
            empresas[nit]["nit"] = nit
            fila_tuple = tuple(fila.get(c) for c in COLS_FIJAS + todas_cols_examenes)
            empresas[nit]["pacientes"].append(fila_tuple)

        if sin_nit:
            archivos = sorted({str(f.get("_archivo") or "?") for f in sin_nit})
            self._log.error("  " + str(len(sin_nit)) + " filas SIN NIT: no se facturan "
                            "y no quedan en ninguna factura. Archivos: " +
                            ", ".join(archivos)[:300])
            for f in sin_nit[:20]:
                self._log.error("      " + str(f.get("Paciente")) + " | " +
                                str(f.get("Empresa")) + " | " + str(f.get("_archivo") or ""))
        return empresas

    # ── Una factura por empresa (Pipeline.py:1011-1298) ─────────────────────
    def _crear_factura(self, nit, datos, todas_cols_examenes):
        cfg = self._config
        settings = self._settings
        registry = self._registry
        log = self._log
        nombre = datos["nombre"]
        pacientes = datos["pacientes"]

        log.info("  Empresa: " + nombre + " | NIT: " + nit +
                 " | Pacientes: " + str(len(pacientes)))

        # Cobro doble: mismo paciente e ingreso en varias filas con el MISMO examen.
        avisos = []
        idx_ced = COLS_FIJAS.index("N Identificacion")
        idx_ing = COLS_FIJAS.index("Ingreso")
        porpaciente = defaultdict(list)
        for p in pacientes:
            porpaciente[(str(p[idx_ced]), str(p[idx_ing]))].append(p)
        for (ced, ing), grupo in porpaciente.items():
            if len(grupo) < 2:
                continue
            cuenta_cod = Counter()
            for p in grupo:
                for i, cod in enumerate(todas_cols_examenes):
                    if cod and p[NUM_COLS_FIJAS + i]:
                        cuenta_cod[cod] += 1
            repes = sorted(c for c, n in cuenta_cod.items() if n > 1)
            if repes:
                aviso = ("OJO cobro doble: el paciente " + ced + " (ingreso " + ing +
                         ") esta en " + str(len(grupo)) + " filas y repite " +
                         ", ".join(repes))
                avisos.append(aviso)
                log.warning("  " + aviso)

        def _con_avisos(detalle):
            return (detalle + " || " + " || ".join(avisos)) if avisos else detalle

        nombre_norm = normalizar(str(nombre or ""))
        for prefijo, razon in settings.empresas_bloqueadas.items():
            if nombre_norm.startswith(normalizar(prefijo)):
                motivo = "NO SE PUEDE SUBIR - " + razon
                log.warning("  " + motivo + " -> VERIFICAR (no se crea)")
                registry.registrar_sin_factura(nit, nombre, pacientes, todas_cols_examenes, motivo)
                return "VERIFICAR", _con_avisos(motivo + " | " + nombre + " (NIT " + str(nit) + ")"), 0, ""

        nit_limpio = limpiar_nit(nit)
        if nit_limpio in settings.ya_subidas:
            factura_id = settings.ya_subidas[nit_limpio]
            log.info("  YA SUBIDA en una corrida anterior -> factura ID " +
                     str(factura_id) + " (no se vuelve a crear)")
            return ("OK", _con_avisos("Ya subida antes (no se duplico). Factura ID " +
                    str(factura_id)), factura_id, self.url_factura(factura_id))

        if nit_limpio in settings.nits_bloqueados:
            motivo = "NIT bloqueado: " + settings.nits_bloqueados[nit_limpio]
            log.warning("  " + motivo + " -> VERIFICAR (no se crea)")
            registry.registrar_sin_factura(nit, nombre, pacientes, todas_cols_examenes, motivo)
            return "VERIFICAR", _con_avisos(motivo + " | " + nombre), 0, ""

        cliente_id, cliente_nombre, metodo = self._buscar_cliente(nit, nombre)

        # Cliente no encontrado: NUNCA se crea (ADR-010); siempre VERIFICAR.
        if not cliente_id:
            if not nit_valido(nit):
                motivo = "NIT invalido en la pre-factura: '" + str(nit) + "'"
            else:
                motivo = "Sin tercero con N. identificacion = " + nit + " en Odoo"
            log.warning("  " + motivo + " -> VERIFICAR (no se crea)")
            registry.registrar_sin_factura(nit, nombre, pacientes, todas_cols_examenes, motivo)
            return "VERIFICAR", _con_avisos(motivo + " | " + nombre), 0, ""

        log.info("  Cliente por " + metodo + ": " + str(cliente_nombre))

        tax_id_renta = self._buscar_tax_id(cfg["taxes"][0])
        tax_id_compras = self._buscar_tax_id(cfg["taxes"][1])
        uom_id = self._buscar_uom_id(cfg["nombre_uom"])

        tax_ids = []
        if tax_id_renta:
            tax_ids.append(tax_id_renta)
        if tax_id_compras:
            tax_ids.append(tax_id_compras)
        if tax_ids:
            log.info("  Impuestos a aplicar: " + str(tax_ids))
        else:
            log.warning("  Ningun impuesto de autorretencion encontrado — lineas sin impuesto")

        idx_ciudad = COLS_FIJAS.index("Ciudad")
        idx_sede = COLS_FIJAS.index("Sede")

        # Cuenta de cada paciente (sede + ciudad); lo que no se imputa con certeza se aparta.
        conteo = defaultdict(int)
        cuenta_nom = {}
        pendientes = []
        cache_ciudad = {}

        for paciente in pacientes:
            ciudad_raw = paciente[idx_ciudad]
            sede_raw = paciente[idx_sede]
            clave_c = (clave_ciudad(ciudad_raw), clave_ciudad(sede_raw))
            if clave_c not in cache_ciudad:
                cache_ciudad[clave_c] = self._resolver.resolver(ciudad_raw, sede_raw)
            cuenta_id, etiqueta, motivo = cache_ciudad[clave_c]

            examenes = [(cod, paciente[NUM_COLS_FIJAS + i])
                        for i, cod in enumerate(todas_cols_examenes)
                        if cod and paciente[NUM_COLS_FIJAS + i]]

            if not cuenta_id:
                for cod, valor in examenes:
                    pendientes.append(registry.pendiente(paciente, nit, nombre, cod, valor,
                                                         "SIN CUENTA ANALITICA", motivo))
                continue

            cuenta_nom[cuenta_id] = etiqueta
            for cod, _valor in examenes:
                conteo[(cod, cuenta_id)] += 1

        if pendientes:
            ciudades = sorted({p["ciudad"] for p in pendientes})
            log.warning("  APARTADOS " + str(len(pendientes)) +
                        " examenes por ciudad sin cuenta: " + ", ".join(ciudades))

        lineas = []
        no_encontrados = []

        for (codigo, cuenta_id), cantidad in sorted(conteo.items(), key=lambda x: str(x[0])):
            prod = self._gateway.find_product(codigo)
            if not prod:
                if codigo not in no_encontrados:
                    no_encontrados.append(codigo)
                i = todas_cols_examenes.index(codigo)
                for paciente in pacientes:
                    valor = paciente[NUM_COLS_FIJAS + i]
                    if not valor:
                        continue
                    # Solo pacientes con ciudad resuelta: los otros ya están apartados.
                    clave_p = (clave_ciudad(paciente[idx_ciudad]),
                               clave_ciudad(paciente[idx_sede]))
                    if cache_ciudad.get(clave_p, (None,))[0]:
                        pendientes.append(registry.pendiente(
                            paciente, nit, nombre, codigo, valor, "PRODUCTO NO ENCONTRADO",
                            "No hay producto con referencia '" + codigo + "' en Odoo"))
                continue

            cuenta_linea = (cfg["cuenta_ingresos_gravados"]
                            if prod["default_code"] in cfg["productos_gravados"]
                            else cfg["cuenta_ingresos_excluidos"])

            cuenta_analitica_id = cuenta_id
            cuenta_c = cuenta_nom.get(cuenta_id, str(cuenta_id))

            linea = {
                "product_id": prod["id"],
                "quantity": cantidad,
                "price_unit": prod["list_price"],
                "name": prod["name"],
                "account_id": cuenta_linea,
            }
            if tax_ids:
                linea["tax_ids"] = [(6, 0, tax_ids)]
            if uom_id:
                linea["product_uom_id"] = uom_id
            if cuenta_analitica_id:
                linea["analytic_account_id"] = cuenta_analitica_id

            lineas.append((0, 0, linea))
            log.info("  Linea: " + codigo + " x" + str(cantidad) +
                     " @ $" + str(prod["list_price"]) +
                     " | analitica: " + str(cuenta_c) +
                     " | taxes: " + str(tax_ids) +
                     " | uom: " + str(uom_id))

        # Cuadre: todo examen del archivo está en una línea o en pendientes.
        examenes_archivo = sum(
            1 for p in pacientes for i, cod in enumerate(todas_cols_examenes)
            if cod and p[NUM_COLS_FIJAS + i])
        en_lineas = sum(linea[2]["quantity"] for linea in lineas)
        if en_lineas + len(pendientes) != examenes_archivo:
            descuadre = ("DESCUADRE: el archivo trae " + str(examenes_archivo) +
                         " examenes, la factura lleva " + str(int(en_lineas)) +
                         " y se apartaron " + str(len(pendientes)) + " (faltan " +
                         str(examenes_archivo - int(en_lineas) - len(pendientes)) + ")")
            avisos.append(descuadre)
            log.error("  " + descuadre)
        else:
            log.info("  Cuadre OK: " + str(examenes_archivo) + " examenes = " +
                     str(int(en_lineas)) + " facturados + " + str(len(pendientes)) +
                     " apartados")

        if not lineas:
            registry.guardar_pendientes(pendientes, "")
            motivo = ("Ninguna linea se pudo armar. " +
                      ("Ciudades sin cuenta: " +
                       ", ".join(sorted({p["ciudad"] for p in pendientes})) + ". "
                       if pendientes else "") +
                      ("Sin producto en Odoo: " + str(no_encontrados)
                       if no_encontrados else ""))
            log.warning("  " + motivo + " -> VERIFICAR (no se crea)")
            registry.registrar_sin_factura(nit, nombre, pacientes, todas_cols_examenes, motivo)
            return "VERIFICAR", _con_avisos(motivo)[:1000], 0, ""

        # Sin fechas: Odoo las asigna al confirmar; el vencimiento se borra tras crear.
        factura_vals = {
            "move_type": "out_invoice",
            "partner_id": cliente_id,
            "journal_id": cfg["diario_id"],
            "state": "draft",
            "narration": "Pre-factura automatica. Pacientes: " + str(len(pacientes)),
            "invoice_line_ids": lineas,
        }

        # Guarda anti-duplicados: borrador equivalente creado hoy por este usuario.
        # create_date está en UTC y se compara con la medianoche local (E-10, se copia).
        inicio_hoy = self._now().strftime("%Y-%m-%d") + " 00:00:00"
        ya = self._gateway.find_today_drafts(cliente_id, cfg["diario_id"], inicio_hoy)
        if ya:
            factura_id = ya[0]["id"]
            log.warning("  YA EXISTIA factura borrador ID " + str(factura_id) +
                        " para este cliente hoy — no se duplica")
            registry.guardar_pendientes(pendientes, factura_id)
            return ("OK", _con_avisos("Ya existia (no se duplico). Factura ID " +
                    str(factura_id)), factura_id, self.url_factura(factura_id))

        factura_id = self._gateway.create_invoice(factura_vals)
        self._limpiar_fecha_vencimiento(factura_id)

        link = self.url_factura(factura_id)
        log.info("  FACTURA ID: " + str(factura_id) + " | Lineas: " + str(len(lineas)))
        log.info("  LINK: " + link)

        registry.guardar_pendientes(pendientes, factura_id)

        msg = ("Factura ID " + str(factura_id) +
               " | " + str(len(lineas)) + " lineas" +
               " | " + str(len(pacientes)) + " pacientes")
        if no_encontrados:
            msg += " | Sin producto en Odoo: " + str(no_encontrados)
        if pendientes:
            msg += (" | FALTAN " + str(len(pendientes)) + " examenes (" +
                    ", ".join(sorted({p["ciudad"] for p in pendientes})) +
                    ") — ver pendientes_facturador.xlsx")
        if avisos:
            msg += " || " + " || ".join(avisos)

        return "OK", msg, factura_id, link

    # ── Corrida completa (Pipeline.py:1672-1912) ────────────────────────────
    def _hora(self):
        return self._now().strftime("%Y-%m-%d %H:%M:%S")

    def _chequeo_previo(self, input_dir):
        s = self._settings
        log = self._log
        log.info("CHEQUEO PREVIO — revisar antes de seguir")
        log.info("  Carpeta de entrada: " + str(input_dir))
        actualizar = self._config["actualizar_precios"]
        log.info("  Actualizar precios: " + str(actualizar) +
                 ("" if actualizar else
                  "  (las lineas suben en 1; el precio se trae a mano en Odoo)"))
        if s.ya_subidas:
            log.warning("  YA_SUBIDAS tiene " + str(len(s.ya_subidas)) + " NIT: a esas "
                        "empresas NO se les crea factura en esta corrida.")
            for n, fid in s.ya_subidas.items():
                log.warning("      " + n + " -> se reporta la factura " + str(fid))
            log.warning("  Si son de un lote anterior, VACIAR YA_SUBIDAS antes de correr.")
        if s.nits_bloqueados:
            log.warning("  NITS_BLOQUEADOS: " + ", ".join(s.nits_bloqueados) +
                        " — no se facturan hasta que se resuelvan")
        if s.empresas_bloqueadas:
            log.warning("  EMPRESAS_BLOQUEADAS: " + ", ".join(s.empresas_bloqueadas))

    def execute(self, input_dir: Path) -> dict | None:
        log = self._log
        log.info("SOANDES — INYECCION MASIVA DE PRE-FACTURAS")
        log.info("  Entrada:   " + str(input_dir))

        archivos = self._source.list_files(input_dir)
        if not archivos:
            log.error("No se encontraron archivos en: " + str(input_dir),
                      user_msg=f"No hay pre-facturas (.xlsx) en {input_dir}.")
            return None
        log.info(str(len(archivos)) + " archivo(s) encontrado(s)")
        self._chequeo_previo(input_dir)

        # ── FASE 1: leer y consolidar ──
        todas_las_filas = []
        todas_cols_exam = []
        archivos_con_error = []
        for ruta in archivos:
            nombre = Path(ruta).name
            try:
                filas, cols_examenes, n_filas = self._source.read(ruta)
                for f in filas:
                    f["_archivo"] = nombre
                todas_las_filas.extend(filas)
                for col in cols_examenes:
                    if col not in todas_cols_exam:
                        todas_cols_exam.append(col)
                log.info("  OK: " + nombre + " | " + str(n_filas) +
                         " pacientes | " + str(len(cols_examenes)) + " examenes")
            except Exception as e:
                log.error("  ERROR leyendo " + nombre + ": " + str(e))
                archivos_con_error.append((nombre, str(e)))
                self._writer.copy_to_verificar(ruta)

        log.info("Total pacientes: " + str(len(todas_las_filas)))
        log.info("Total examenes:  " + str(len(todas_cols_exam)))

        periodos = Counter(str(f["Base"]) for f in todas_las_filas if f.get("Base"))
        for base, n in periodos.most_common(12):
            log.info("  " + str(n).rjust(6) + "  " + base)
        if len(periodos) > 1:
            meses = {p.split()[-2] if len(p.split()) > 1 else p for p in periodos}
            if len(meses) > 1:
                log.warning("  OJO: hay MAS DE UN MES en la carpeta (" +
                            ", ".join(sorted(meses)) + "). Confirmar que es lo que "
                            "se quiere facturar antes de seguir.",
                            user_msg="Atención: las pre-facturas traen más de un mes en la columna Base (" +
                                     ", ".join(sorted(meses)) + ").")

        # ── FASE 2: agrupar ──
        empresas = self._agrupar_por_empresa(todas_las_filas, todas_cols_exam)
        log.info("Empresas unicas: " + str(len(empresas)))

        # ── FASE 3: conectar ──
        self._gateway.connect()

        # ── FASE 4: inyectar ──
        resultados = [{
            "nit": "", "empresa": nombre_arch, "estado": "ERROR",
            "detalle": "NO SE PUDO LEER EL ARCHIVO — " + err,
            "factura_id": "", "link": "", "total": "", "precios": "",
            "hora": self._hora(),
        } for nombre_arch, err in archivos_con_error]
        total_emp = len(empresas)

        self._writer.start_created_log()

        progreso = self._progress("Cargando pre-facturas en Odoo", total_emp) if self._progress else None
        if progreso:
            progreso.__enter__()
        try:
            for i, (nit, datos) in enumerate(empresas.items(), 1):
                self._procesar_empresa(i, total_emp, nit, datos, todas_cols_exam, resultados)
                if progreso:
                    progreso.advance()
        finally:
            if progreso:
                progreso.__exit__(None, None, None)

        self._writer.write_books(resultados, self._registry, self.url_factura)
        return self._resumen(archivos, archivos_con_error, total_emp, resultados)

    def _procesar_empresa(self, i, total_emp, nit, datos, todas_cols_exam, resultados):
        log = self._log
        hora = self._hora()
        log.info("[" + str(i) + "/" + str(total_emp) + "] " + datos["nombre"])

        # Reintenta solo ante caídas de red; la guarda anti-duplicados lo hace seguro.
        estado = detalle = None
        factura_id, link = 0, ""
        for intento in range(3):
            try:
                estado, detalle, factura_id, link = self._crear_factura(nit, datos, todas_cols_exam)
                break
            except (OSError, xmlrpc.client.ProtocolError) as e:
                log.warning("  Fallo de red (" + str(e)[:80] + ")")
                if intento < 2:
                    log.warning("  Reintentando en 10 segundos...")
                    self._sleep(10)
                    try:
                        self._gateway.connect()
                    except Exception:
                        pass
                else:
                    estado, detalle, factura_id, link = "ERROR", "Red: " + str(e)[:130], 0, ""
                    log.error("  ERROR de red tras 3 intentos")
            except Exception as e:
                estado, detalle, factura_id, link = "ERROR", str(e)[:150], 0, ""
                log.error("  ERROR: " + detalle, exc_info=True)
                break

        total_fact, estado_precios = "", ""
        if factura_id and self._config["actualizar_precios"]:
            ok_precio, motivo, total_fact = self._actualizar_precios(factura_id)
            if ok_precio:
                estado_precios = "ACTUALIZADOS"
                log.info("  Precios actualizados | Total: $" + format(total_fact, ",.0f"))
            else:
                estado_precios = "SIN TARIFA"
                total_fact = ""
                detalle = (detalle + " || PRECIOS EN 1: " + motivo)[:1000]
                log.warning("  Precios NO actualizados: " + motivo[:160])

        if factura_id:
            self._writer.append_created(factura_id, nit, datos["nombre"], self.url_factura(factura_id))

        resultados.append({
            "nit": nit,
            "empresa": datos["nombre"],
            "estado": estado,
            "detalle": detalle,
            "factura_id": factura_id if factura_id else "",
            "link": link,
            "total": total_fact,
            "precios": estado_precios,
            "hora": hora,
        })

        if i % 10 == 0:
            self._writer.write_books(resultados, self._registry, self.url_factura)

    def _resumen(self, archivos, archivos_con_error, total_emp, resultados) -> dict:
        log = self._log
        reg = self._registry
        ok = sum(1 for r in resultados if r["estado"] == "OK")
        verificar = sum(1 for r in resultados if r["estado"] == "VERIFICAR")
        errores = sum(1 for r in resultados if r["estado"] == "ERROR")

        log.info("RESUMEN FINAL")
        log.info("  Archivos en la carpeta: " + str(len(archivos)))
        for nombre_arch, err in archivos_con_error:
            log.error("      " + nombre_arch + " — " + err[:110])
        log.info("  Empresas procesadas: " + str(total_emp))
        log.info("  Exitosas:            " + str(ok))
        log.info("  Para verificar:      " + str(verificar))
        log.info("  Errores:             " + str(errores))
        if self._config["actualizar_precios"]:
            con_prec = sum(1 for r in resultados if r.get("precios") == "ACTUALIZADOS")
            sin_prec = sum(1 for r in resultados if r.get("precios") == "SIN TARIFA")
            facturado = sum(r["total"] for r in resultados
                            if isinstance(r.get("total"), (int, float)))
            log.info("  Precios OK:          " + str(con_prec))
            log.info("  Precios sin tarifa:  " + str(sin_prec) + "  (quedaron en 1)")
            log.info("  Total facturado:     $" + format(facturado, ",.0f"))
        if reg.pendientes:
            valor = sum(p["valor"] for p in reg.pendientes
                        if isinstance(p["valor"], (int, float)))
            log.warning("  SIN SUBIR:           " + str(len(reg.pendientes)) +
                        " examenes de " + str(len({p["cedula"] for p in reg.pendientes})) +
                        " pacientes  ($" + format(valor, ",.0f") + " segun el archivo)")
        if reg.sin_factura:
            porcrear = [e for e in reg.sin_factura if e["que_falta"] == "NIT POR CREAR"]
            log.warning("  SIN FACTURAR:        " + str(len(reg.sin_factura)) + " empresas, " +
                        str(sum(e["pacientes"] for e in reg.sin_factura)) + " pacientes  ($" +
                        format(sum(e["valor"] for e in reg.sin_factura), ",.0f") + ")")
            if porcrear:
                log.warning("  NIT POR CREAR:       " + str(len(porcrear)) +
                            " terceros que no existen en Odoo  ($" +
                            format(sum(e["valor"] for e in porcrear), ",.0f") + ")")

        partes = [f"{total_emp} empresa(s): {ok} OK, {verificar} para verificar, {errores} con error"]
        if archivos_con_error:
            partes.append(f"{len(archivos_con_error)} archivo(s) no se pudieron leer (copiados a verificar/)")
        if reg.pendientes:
            partes.append(f"{len(reg.pendientes)} examen(es) quedaron por subir a mano")
        log.info("Carga de pre-facturas terminada",
                 user_msg="Carga de pre-facturas: " + "; ".join(partes) + ". Revisa los libros de la corrida.")
        return {
            "archivos": len(archivos), "archivos_con_error": len(archivos_con_error),
            "empresas": total_emp, "ok": ok, "verificar": verificar, "errores": errores,
            "pendientes": len(reg.pendientes), "sin_factura": len(reg.sin_factura),
        }
