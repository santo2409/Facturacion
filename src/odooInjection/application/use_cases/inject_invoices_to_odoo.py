from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from src.odooInjection.domain.entities.invoice_result import InvoiceResult
from src.odooInjection.domain.repositories.odoo_connection_repository import (
    OdooConnectionRepository,
)
from src.odooInjection.domain.repositories.pre_invoice_reader_repository import (
    PreInvoiceReaderRepository,
)
from src.odooInjection.domain.services.city_account_resolver import CityAccountResolver


class InjectInvoicesToOdoo:
    def __init__(
        self,
        odoo_repo: OdooConnectionRepository,
        reader_repo: PreInvoiceReaderRepository,
        city_resolver: CityAccountResolver,
        log_generator,
        progress,
        logger,
        config: dict,
    ):
        self.odoo_repo = odoo_repo
        self.reader_repo = reader_repo
        self.city_resolver = city_resolver
        self.log_generator = log_generator
        self.progress = progress
        self.logger = logger
        self.config = config

    def execute(self, input_dir: Path, output_dir: Path):
        self.logger.info(
            f"Leyendo pre-facturas de {input_dir}",
            user_msg="Leyendo archivos de pre-facturas...",
        )
        filas, cols_examenes = self.reader_repo.read_files(input_dir)
        if not filas:
            self.logger.warning(
                "No se encontraron datos en pre-facturas",
                user_msg="No se encontraron datos para inyectar.",
            )
            return []

        self.logger.info(f"Total pacientes: {len(filas)} | Exámenes: {len(cols_examenes)}")

        empresas = self._agrupar_por_empresa(filas, cols_examenes)

        # Anti-duplicados: excluir NITs ya exitosos en log previo
        log_path = output_dir / "log_inyeccion.xlsx"
        nits_ok = self.log_generator.read_successful_nits(log_path)
        if nits_ok:
            antes = len(empresas)
            empresas = {k: v for k, v in empresas.items() if k not in nits_ok}
            omitidos = antes - len(empresas)
            if omitidos:
                self.logger.info(
                    f"{omitidos} empresa(s) omitida(s) por ya estar en log con estado OK",
                    user_msg=f"{omitidos} empresa(s) ya procesada(s) anteriormente, se omiten.",
                )
        if not empresas:
            self.logger.info("Todas las empresas ya fueron procesadas.", user_msg="No hay empresas nuevas por inyectar.")
            return []

        self.logger.info(
            f"Empresas únicas: {len(empresas)}",
            user_msg=f"{len(empresas)} empresas a procesar.",
        )

        self.odoo_repo.connect()

        tax_ids = self._resolve_taxes()
        uom_id = self.odoo_repo.find_uom(self.config["nombre_uom"])

        resultados = []
        total = len(empresas)

        with self.progress("Inyectando facturas en Odoo", total=total):
            for nit, datos in empresas.items():
                hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result = self._procesar_empresa(
                    nit, datos, cols_examenes, tax_ids, uom_id
                )
                result.hora = hora
                resultados.append(result)
                self.progress.advance()

        self.log_generator.generate(resultados, output_dir)

        ok = sum(1 for r in resultados if r.estado == "OK")
        verificar = sum(1 for r in resultados if r.estado == "VERIFICAR")
        errores = sum(1 for r in resultados if r.estado == "ERROR")
        self.logger.info(
            f"Resumen: {ok} OK | {verificar} VERIFICAR | {errores} ERROR",
            user_msg=f"Inyección completada: {ok} exitosas, {verificar} por verificar, {errores} errores.",
        )
        return resultados

    def _resolve_taxes(self) -> list[int]:
        tax_ids = []
        for nombre in self.config.get("taxes", []):
            tid = self.odoo_repo.find_tax(nombre)
            if tid:
                tax_ids.append(tid)
            else:
                self.logger.warning(f"Impuesto no encontrado: '{nombre}'")
        return tax_ids

    def _agrupar_por_empresa(self, filas: list[dict], cols_examenes: list[str]) -> dict:
        empresas = defaultdict(lambda: {"nombre": "", "nit": "", "fecha": "", "pacientes": []})
        for fila in filas:
            nit = str(fila.get("NIT") or "").strip()
            if not nit or nit == "None":
                continue
            empresas[nit]["nombre"] = str(fila.get("Empresa") or "").strip()
            empresas[nit]["nit"] = nit
            fecha_raw = fila.get("Fecha Ingreso")
            if fecha_raw:
                empresas[nit]["fecha"] = str(fecha_raw)[:10]
            empresas[nit]["pacientes"].append(fila)
        return dict(empresas)

    def _procesar_empresa(self, nit, datos, cols_examenes, tax_ids, uom_id) -> InvoiceResult:
        nombre = datos["nombre"]
        pacientes = datos["pacientes"]
        fecha = datos["fecha"]

        try:
            cliente_id, cliente_nombre, metodo = self.odoo_repo.find_client(nit, nombre)

            if not cliente_id:
                cliente_id, cliente_nombre, metodo = self.odoo_repo.find_client_by_name(nombre)

            if not cliente_id:
                return InvoiceResult(nit, nombre, "VERIFICAR", f"Empresa no encontrada en Avancys con NIT: {nit}")

            # Construir líneas agrupadas por (producto, cuenta_analitica)
            conteo = defaultdict(int)
            for paciente in pacientes:
                ciudad_raw = paciente.get("Ciudad")
                cuenta, _, _ = self.city_resolver.resolve(ciudad_raw)
                for codigo in cols_examenes:
                    valor = paciente.get(codigo)
                    if valor and str(valor).strip() not in ("", "0", "0.0", "nan", "NaN"):
                        conteo[(codigo, cuenta)] += 1

            lineas = []
            no_encontrados = []
            for (codigo, cuenta_c), cantidad in conteo.items():
                prod = self.odoo_repo.find_product(codigo)
                if not prod:
                    if codigo not in no_encontrados:
                        no_encontrados.append(codigo)
                    continue

                cuenta_linea = (
                    self.config["cuenta_ingresos_gravados"]
                    if prod["default_code"] in self.config.get("productos_gravados", [])
                    else self.config["cuenta_ingresos_excluidos"]
                )

                cuenta_analitica_id = self.odoo_repo.find_analytic_account(cuenta_c)

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

            if not lineas:
                return InvoiceResult(
                    nit, nombre, "ERROR",
                    f"Sin líneas válidas. No encontrados: {no_encontrados}",
                )

            hoy = datetime.now()
            fecha_fact = hoy.strftime("%Y-%m-%d")
            fecha_venc = (hoy + timedelta(days=self.config["fecha_vencimiento_dias"])).strftime("%Y-%m-%d")

            factura_vals = {
                "move_type": "out_invoice",
                "partner_id": cliente_id,
                "invoice_date": fecha_fact,
                "invoice_date_due": fecha_venc,
                "journal_id": self.config["diario_id"],
                "state": "draft",
                "narration": f"Pre-factura automática. Pacientes: {len(pacientes)}",
                "invoice_line_ids": lineas,
            }
            if self.config.get("fecha_servicio"):
                factura_vals["date_of_service"] = self.config["fecha_servicio"]

            range_id = self.odoo_repo.find_date_range(fecha)
            if range_id:
                factura_vals["range_id"] = range_id

            factura_id = self.odoo_repo.create_invoice(factura_vals)
            link = f"{self.config['url']}/web#id={factura_id}&model=account.move&view_type=form"

            msg = f"Factura ID {factura_id} | {len(lineas)} líneas | {len(pacientes)} pacientes"
            if no_encontrados:
                msg += f" | Sin precio: {no_encontrados}"

            return InvoiceResult(nit, nombre, "OK", msg, factura_id, link)

        except Exception as e:
            self.logger.error(f"Error procesando {nombre}: {e}", exc_info=True)
            return InvoiceResult(nit, nombre, "ERROR", str(e)[:150])
