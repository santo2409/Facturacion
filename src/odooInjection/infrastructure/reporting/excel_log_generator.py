from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.odooInjection.domain.entities.invoice_result import InvoiceResult

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = ["#", "NIT", "Empresa", "Estado", "Detalle", "Factura ID", "Link Odoo", "Fecha/Hora"]
_FILL_OK = PatternFill("solid", fgColor="C6EFCE")
_FILL_VERIFICAR = PatternFill("solid", fgColor="FFEB9C")
_FILL_ERROR = PatternFill("solid", fgColor="FFC7CE")


class ExcelLogGenerator:
    def __init__(self, logger):
        self._logger = logger

    def read_successful_nits(self, log_path: Path) -> set[str]:
        """Lee log_inyeccion.xlsx previo y retorna NITs con estado OK."""
        if not log_path.exists():
            return set()
        try:
            wb = openpyxl.load_workbook(log_path, read_only=True, data_only=True)
            ws = wb.active
            nits = set()
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and len(row) >= 4 and str(row[3]).strip().upper() == "OK":
                    nit = str(row[1]).strip()
                    if nit and nit != "None":
                        nits.add(nit)
            wb.close()
            return nits
        except Exception as e:
            self._logger.warning(
                f"No se pudo leer el log previo de inyección ({log_path}): {e}",
                user_msg=(
                    f"No se pudo leer el log de inyección previo ({log_path.name}); "
                    "verifica que no esté abierto en Excel. Se reprocesarán todas las empresas."
                ),
            )
            return set()

    def _read_previous_results(self, log_path: Path) -> dict[str, InvoiceResult]:
        """Lee el log previo completo (no solo los OK) para fusionarlo con los
        resultados de esta corrida, en vez de sobrescribir el histórico completo."""
        previos: dict[str, InvoiceResult] = {}
        if not log_path.exists():
            return previos
        try:
            wb = openpyxl.load_workbook(log_path, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2):
                nit_cell = row[1] if len(row) > 1 else None
                if nit_cell is None or nit_cell.value in (None, ""):
                    continue
                nit = str(nit_cell.value).strip()
                if not nit or nit == "None":
                    continue
                link_cell = row[6] if len(row) > 6 else None
                link = link_cell.hyperlink.target if link_cell is not None and link_cell.hyperlink else ""
                factura_id = row[5].value if len(row) > 5 and row[5].value not in ("", None) else None
                previos[nit] = InvoiceResult(
                    nit=nit,
                    empresa=str(row[2].value or "") if len(row) > 2 else "",
                    estado=str(row[3].value or "") if len(row) > 3 else "",
                    detalle=str(row[4].value or "") if len(row) > 4 else "",
                    factura_id=factura_id,
                    link=link,
                    hora=str(row[7].value or "") if len(row) > 7 else "",
                )
            wb.close()
        except Exception as e:
            self._logger.error(
                f"No se pudo leer el histórico previo del log de inyección ({log_path}): {e}",
                user_msg=(
                    f"No se pudo leer el histórico previo de {log_path.name}; "
                    "el log de esta corrida solo tendrá las empresas procesadas ahora."
                ),
            )
        return previos

    def generate(self, resultados: list[InvoiceResult], output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "log_inyeccion.xlsx"

        historial = self._read_previous_results(log_path)
        for r in resultados:
            historial[r.nit] = r
        resultados = list(historial.values())

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Log Inyeccion"

        # Header
        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER

        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 15
        ws.column_dimensions["C"].width = 48
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 60
        ws.column_dimensions["F"].width = 12
        ws.column_dimensions["G"].width = 35
        ws.column_dimensions["H"].width = 20
        ws.freeze_panes = "A2"

        # Data rows
        for i, r in enumerate(resultados, 1):
            fila = i + 1
            ws.append([
                i, r.nit, r.empresa, r.estado, r.detalle,
                r.factura_id or "", r.link, r.hora,
            ])

            if r.link:
                celda = ws.cell(row=fila, column=7)
                celda.hyperlink = r.link
                celda.value = "Abrir factura"
                celda.font = Font(name="Arial", size=10, color="1565C0", underline="single")

            fill = (
                _FILL_OK if r.estado == "OK"
                else _FILL_VERIFICAR if r.estado == "VERIFICAR"
                else _FILL_ERROR
            )
            for col in range(1, 9):
                cell = ws.cell(fila, col)
                if col != 7 or not r.link:
                    cell.fill = fill
                    cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER

        # Summary
        ws.append([])
        ok = sum(1 for r in resultados if r.estado == "OK")
        verificar = sum(1 for r in resultados if r.estado == "VERIFICAR")
        errores = sum(1 for r in resultados if r.estado == "ERROR")

        for label, val, color in [
            ("TOTAL", len(resultados), "3D2B6B"),
            ("EXITOSOS", ok, "1A7A4A"),
            ("VERIFICAR", verificar, "E67E22"),
            ("ERRORES", errores, "B71C1C"),
        ]:
            fila = ws.max_row + 1
            ws.cell(fila, 3, label).font = Font(bold=True, name="Arial", color=color)
            ws.cell(fila, 4, val).font = Font(bold=True, name="Arial", color=color)

        wb.save(log_path)
        self._logger.info(
            f"Log Excel guardado: {log_path}",
            user_msg=f"Log de inyección guardado en {log_path}",
        )
