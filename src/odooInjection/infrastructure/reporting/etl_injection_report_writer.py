"""Salidas de la carga de pre-facturas con el formato de ETL-Avancys.

Copia de `generar_log_excel`, `generar_libro_pendientes`, `generar_libro_cuentas` y
`_cabecera` (`Pipeline.py:1388-1667`) y de la escritura de `facturas_creadas.csv`
(`1791-1792`, `1837-1841`). Mismos nombres, hojas, columnas, colores y totales.
Cada corrida escribe en su propia carpeta (D-4).
"""

import shutil
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.odooInjection.domain.repositories.injection_report_writer import (
    InjectionReportWriter,
)

LOG_FILE = "log_inyeccion.xlsx"
LOG_IDS = "facturas_creadas.csv"
LOG_PENDIENTES = "pendientes_facturador.xlsx"
LOG_CUENTAS = "cuentas_por_revisar.xlsx"
CARPETA_VERIFICAR = "verificar"


def _cabecera(ws, headers, anchos):
    thin = Side(style="thin", color="CCCCCC")
    borde = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
        c.fill = PatternFill("solid", fgColor="3D2B6B")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = borde
    for col, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    return borde


class EtlInjectionReportWriter(InjectionReportWriter):
    def __init__(self, output_dir: Path, logger):
        self._dir = Path(output_dir)
        self._logger = logger

    def _carpetas(self) -> None:
        # Se crean al primer uso: una corrida sin archivos no deja carpetas vacías (ADR-014).
        (self._dir / CARPETA_VERIFICAR).mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        return self._dir

    def copy_to_verificar(self, path: Path) -> None:
        self._carpetas()
        shutil.copy(path, self._dir / CARPETA_VERIFICAR / Path(path).name)

    def start_created_log(self) -> None:
        self._carpetas()
        with open(self._dir / LOG_IDS, "w", encoding="utf-8") as fh:
            fh.write("factura_id;nit;empresa;url\n")

    def append_created(self, factura_id, nit, empresa: str, url: str) -> None:
        with open(self._dir / LOG_IDS, "a", encoding="utf-8") as fh:
            fh.write("{};{};{};{}\n".format(factura_id, nit, empresa.replace(";", ","), url))

    def write_books(self, resultados: list[dict], registry, url_factura) -> None:
        self._carpetas()
        self._log_excel(resultados)
        self._libro_pendientes(registry, url_factura)
        self._libro_cuentas(registry)

    # ── pendientes_facturador.xlsx (Pipeline.py:1403-1502) ──────────────────
    def _libro_pendientes(self, registry, url_factura):
        pendientes = registry.pendientes
        sin_factura = registry.sin_factura
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Subir a mano"
        headers = ["NIT", "Empresa", "Factura ID", "Link Odoo", "Paciente",
                   "Identificacion", "Ciudad", "Sede", "Fecha Ingreso",
                   "Tipo Examen", "Codigo examen", "Valor archivo",
                   "Problema", "Por que no se subio"]
        borde = _cabecera(ws, headers, [14, 42, 11, 58, 34, 16, 18, 34, 14,
                                        16, 14, 14, 20, 72])
        rojo = PatternFill("solid", fgColor="FFC7CE")
        amarillo = PatternFill("solid", fgColor="FFEB9C")

        for p in sorted(pendientes, key=lambda x: (str(x["empresa"]), str(x["ciudad"]),
                                                   str(x["codigo"]))):
            link = url_factura(p["factura_id"]) if p["factura_id"] else ""
            ws.append([p["nit"], p["empresa"], p["factura_id"], link, p["paciente"],
                       p["cedula"], p["ciudad"], p["sede"], p["fecha"],
                       p["tipo_examen"], p["codigo"], p["valor"],
                       p["problema"], p["motivo"]])
            fila = ws.max_row
            fill = rojo if p["problema"] == "SIN CUENTA ANALITICA" else amarillo
            for col in range(1, len(headers) + 1):
                celda = ws.cell(fila, col)
                celda.border = borde
                if col == 4 and link:
                    celda.hyperlink = link
                    celda.font = Font(name="Arial", size=9, color="1565C0",
                                      underline="single")
                else:
                    celda.fill = fill
                    celda.font = Font(name="Arial", size=10)
            ws.cell(fila, 12).number_format = "#,##0"
            ws.row_dimensions[fila].height = 16

        if pendientes:
            fila = ws.max_row + 2
            ws.cell(fila, 2, "EXAMENES SIN SUBIR").font = Font(bold=True, name="Arial",
                                                               color="B71C1C")
            ws.cell(fila, 3, len(pendientes)).font = Font(bold=True, name="Arial",
                                                          color="B71C1C")
            total = sum(p["valor"] for p in pendientes
                        if isinstance(p["valor"], (int, float)))
            ws.cell(fila + 1, 2, "VALOR SEGUN EL ARCHIVO").font = Font(bold=True,
                                                                       name="Arial",
                                                                       color="B71C1C")
            c = ws.cell(fila + 1, 3, total)
            c.font = Font(bold=True, name="Arial", color="B71C1C")
            c.number_format = "#,##0"
        else:
            ws.cell(2, 1, "Nada quedo por fuera en esta corrida.").font = Font(
                name="Arial", size=10, italic=True)

        ws2 = wb.create_sheet("Empresas sin factura")
        headers2 = ["Que falta", "NIT", "Empresa (pre-factura)", "Pacientes",
                    "Examenes", "Valor archivo", "Por que no se facturo",
                    "Que hay que hacer"]
        borde2 = _cabecera(ws2, headers2, [17, 15, 50, 11, 11, 15, 68, 72])
        for e in sorted(sin_factura, key=lambda x: -x["valor"]):
            ws2.append([e["que_falta"], e["nit"], e["empresa"], e["pacientes"],
                        e["examenes"], e["valor"], e["motivo"], e["accion"]])
            fila = ws2.max_row
            fill = rojo if e["que_falta"] == "NIT POR CREAR" else amarillo
            for col in range(1, len(headers2) + 1):
                celda = ws2.cell(fila, col)
                celda.fill = fill
                celda.font = Font(name="Arial", size=10)
                celda.border = borde2
                celda.alignment = Alignment(vertical="top", wrap_text=(col >= 7))
            ws2.cell(fila, 2).number_format = "@"
            ws2.cell(fila, 6).number_format = "#,##0"

        if sin_factura:
            fila = ws2.max_row + 2
            porcrear = [e for e in sin_factura if e["que_falta"] == "NIT POR CREAR"]
            for etiqueta, valor in [
                ("EMPRESAS SIN FACTURAR", len(sin_factura)),
                ("   de esas, por NIT que no existe", len(porcrear)),
                ("PACIENTES SIN FACTURAR", sum(e["pacientes"] for e in sin_factura)),
                ("VALOR SEGUN EL ARCHIVO", sum(e["valor"] for e in sin_factura)),
            ]:
                ws2.cell(fila, 3, etiqueta).font = Font(bold=True, name="Arial",
                                                        color="B71C1C")
                c = ws2.cell(fila, 4, valor)
                c.font = Font(bold=True, name="Arial", color="B71C1C")
                c.number_format = "#,##0"
                fila += 1
        else:
            ws2.cell(2, 1, "Todas las empresas se facturaron.").font = Font(
                name="Arial", size=10, italic=True)

        ruta = self._dir / LOG_PENDIENTES
        wb.save(ruta)
        self._logger.info("Pendientes del facturador: " + str(ruta))

    # ── cuentas_por_revisar.xlsx (Pipeline.py:1504-1566) ────────────────────
    def _libro_cuentas(self, registry):
        revisar = registry.revisar
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Arreglar en Odoo"
        headers = ["Problema", "Ciudad / Codigo", "Examenes sin subir", "Pacientes",
                   "Empresas", "Valor archivo", "Sedes que aparecen",
                   "Por que no se pudo subir", "Que hay que hacer"]
        borde = _cabecera(ws, headers, [20, 26, 17, 11, 10, 15, 50, 86, 76])
        rojo = PatternFill("solid", fgColor="FFC7CE")
        amarillo = PatternFill("solid", fgColor="FFEB9C")

        def accion(r):
            if r["problema"] == "PRODUCTO NO ENCONTRADO":
                return ("NO se agrego a la factura: no existe el producto '" +
                        str(r["que"]) + "' en Odoo. Hay que agregar esa linea "
                        "A MANO, paciente por paciente (ver la hoja 'Subir a "
                        "mano'). Va a seguir saliendo aqui cada mes mientras el "
                        "producto no exista con esa referencia exacta")
            if "SEDE_CUENTA" in r["motivo"]:
                return ("La sede esta mapeada a una cuenta de otra ciudad: "
                        "revisar la tabla SEDE_CUENTA del script. La linea hay "
                        "que agregarla A MANO")
            if "no esta en el mapa" in r["motivo"]:
                return ("NO se agrego a la factura: hay que agregar esas lineas A "
                        "MANO. Para la proxima corrida, buscar la cuenta "
                        "analitica de esta ciudad en Odoo y agregarla a "
                        "CIUDAD_CUENTA (por codigo) o a CIUDAD_CUENTA_ID (si la "
                        "cuenta no tiene codigo). Si no existe, crearla primero")
            if "repetido" in r["motivo"]:
                return ("NO se agrego a la factura: agregar las lineas A MANO. En "
                        "Odoo hay varias cuentas con ese mismo codigo — darle un "
                        "codigo propio a la de esta ciudad, o cargarla por id en "
                        "CIUDAD_CUENTA_ID")
            if "no existe en Odoo" in r["motivo"]:
                return ("NO se agrego a la factura: agregar A MANO. Crear la "
                        "cuenta analitica, o corregir el codigo del mapa")
            if "no trae ciudad" in r["motivo"]:
                return ("NO se agrego a la factura: agregar A MANO y completar la "
                        "columna Ciudad en la pre-factura")
            return "NO se agrego a la factura: agregar A MANO y revisar con el facturador"

        for r in sorted(revisar.values(), key=lambda x: (-x["examenes"], str(x["que"]))):
            ws.append([r["problema"], r["que"], r["examenes"], len(r["pacientes"]),
                       len(r["empresas"]), r["valor"],
                       ", ".join(sorted(r["sedes"]))[:200], r["motivo"], accion(r)])
            fila = ws.max_row
            fill = rojo if r["problema"] == "SIN CUENTA ANALITICA" else amarillo
            for col in range(1, len(headers) + 1):
                celda = ws.cell(fila, col)
                celda.fill = fill
                celda.font = Font(name="Arial", size=10)
                celda.border = borde
                celda.alignment = Alignment(vertical="top", wrap_text=(col >= 7))
            ws.cell(fila, 6).number_format = "#,##0"

        if not revisar:
            ws.cell(2, 1, "Todas las ciudades y codigos del lote se resolvieron.").font = \
                Font(name="Arial", size=10, italic=True)

        ruta = self._dir / LOG_CUENTAS
        wb.save(ruta)
        self._logger.info("Cuentas por revisar: " + str(ruta))

    # ── log_inyeccion.xlsx (Pipeline.py:1571-1667) ──────────────────────────
    def _log_excel(self, resultados):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Log Inyeccion"

        thin = Side(style="thin", color="CCCCCC")
        borde = Border(left=thin, right=thin, top=thin, bottom=thin)

        headers = ["#", "NIT", "Empresa", "Estado", "Detalle", "Factura ID", "Link Odoo",
                   "Total", "Precios", "Fecha/Hora"]
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = borde

        for letra, ancho in zip("ABCDEFGHIJ", (5, 15, 48, 12, 60, 12, 62, 14, 14, 20)):
            ws.column_dimensions[letra].width = ancho
        ws.row_dimensions[1].height = 22
        ws.freeze_panes = "A2"

        verde = PatternFill("solid", fgColor="C6EFCE")
        rojo = PatternFill("solid", fgColor="FFC7CE")
        amarillo = PatternFill("solid", fgColor="FFEB9C")
        gris = PatternFill("solid", fgColor="F5F5F5")
        naranja = PatternFill("solid", fgColor="FCD5B4")

        for i, r in enumerate(resultados, 1):
            fila = i + 1
            link = r.get("link", "")
            ws.append([i, r["nit"], r["empresa"], r["estado"],
                       r["detalle"], r["factura_id"] or "", link,
                       r.get("total", ""), r.get("precios", ""), r["hora"]])

            if link:
                celda_link = ws.cell(row=fila, column=7)
                celda_link.hyperlink = link
                celda_link.value = link
                celda_link.font = Font(name="Arial", size=9,
                                       color="1565C0", underline="single")

            fill = (verde if r["estado"] == "OK" else
                    amarillo if r["estado"] == "VERIFICAR" else
                    rojo if r["estado"] == "ERROR" else gris)
            for col in range(1, len(headers) + 1):
                if col != 7 or not link:
                    ws.cell(fila, col).fill = fill
                    ws.cell(fila, col).font = Font(name="Arial", size=10)
                ws.cell(fila, col).border = borde

            ws.cell(fila, 8).number_format = "#,##0"
            if r.get("precios") == "SIN TARIFA":
                ws.cell(fila, 9).fill = naranja
                ws.cell(fila, 9).font = Font(name="Arial", size=10, bold=True,
                                             color="8A4B00")
            ws.row_dimensions[fila].height = 16

        ws.append([])
        total = len(resultados)
        ok = sum(1 for r in resultados if r["estado"] == "OK")
        verificar = sum(1 for r in resultados if r["estado"] == "VERIFICAR")
        errores = sum(1 for r in resultados if r["estado"] == "ERROR")
        con_prec = sum(1 for r in resultados if r.get("precios") == "ACTUALIZADOS")
        sin_prec = sum(1 for r in resultados if r.get("precios") == "SIN TARIFA")
        facturado = sum(r["total"] for r in resultados
                        if isinstance(r.get("total"), (int, float)))

        for label, val, color in [
            ("TOTAL", total, "3D2B6B"),
            ("EXITOSOS", ok, "1A7A4A"),
            ("VERIFICAR", verificar, "E67E22"),
            ("ERRORES", errores, "B71C1C"),
            ("PRECIOS OK", con_prec, "1A7A4A"),
            ("PRECIOS SIN TARIFA", sin_prec, "8A4B00"),
            ("TOTAL FACTURADO", facturado, "3D2B6B"),
        ]:
            fila = ws.max_row + 1
            ws.cell(fila, 3, label).font = Font(bold=True, name="Arial", color=color)
            celda = ws.cell(fila, 4, val)
            celda.font = Font(bold=True, name="Arial", color=color)
            if label == "TOTAL FACTURADO":
                celda.number_format = "#,##0"

        ruta = self._dir / LOG_FILE
        wb.save(ruta)
        self._logger.info("Log Excel guardado: " + str(ruta))
