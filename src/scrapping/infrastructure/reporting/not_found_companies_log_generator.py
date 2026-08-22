from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.scrapping.domain.entities.nit_result import NitResult

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = ["#", "NIT", "Empresa", "Estado", "Base Consultada", "Fecha/Hora"]
_FILL_NO_ENCONTRADO = PatternFill("solid", fgColor="FFEB9C")
_FILL_FALTA_ODOO = PatternFill("solid", fgColor="FFD966")

ESTADO_NO_ENCONTRADO = "No encontrado (ni Odoo ni RUES)"
ESTADO_FALTA_ODOO = "Existe en RUES, falta en Odoo"


class NotFoundCompaniesLogGenerator:
    """Genera logs/empresas_no_encontradas.xlsx: registro de NITs pendientes de
    verificación manual, en dos estados posibles (principio 'VERIFICAR, nunca
    crear' para el primero):
    - No encontrado (ni Odoo ni RUES): no se creó en ningún sistema.
    - Existe en RUES, falta en Odoo: se creó localmente con el dato de RUES,
      pero falta crearlo en Odoo/Avancys antes de facturar.
    Se fusiona con corridas anteriores (igual que log_inyeccion.xlsx) y un NIT
    sale del log en cuanto queda resuelto en ambos sistemas en una corrida
    posterior."""

    FILENAME = "empresas_no_encontradas.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def _read_previous(self, log_path: Path) -> dict[str, dict]:
        previos: dict[str, dict] = {}
        if not log_path.exists():
            return previos
        try:
            wb = openpyxl.load_workbook(log_path, data_only=True)
            ws = wb.active
            header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
            col_index = {
                str(name).strip(): idx
                for idx, name in enumerate(header_row)
                if name
            }
            idx_nit = col_index.get("NIT")
            idx_empresa = col_index.get("Empresa")
            idx_estado = col_index.get("Estado")
            idx_bases = col_index.get("Base Consultada")
            idx_fecha = col_index.get("Fecha/Hora")

            if idx_nit is None:
                return previos

            def _cell(row, idx):
                return row[idx] if idx is not None and idx < len(row) else None

            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or _cell(row, idx_nit) in (None, ""):
                    continue
                nit = str(_cell(row, idx_nit)).strip()
                if not nit or nit == "None":
                    continue
                empresa = _cell(row, idx_empresa)
                estado = _cell(row, idx_estado)
                bases = _cell(row, idx_bases)
                fecha = _cell(row, idx_fecha)
                previos[nit] = {
                    "empresa": str(empresa) if empresa else "",
                    "estado": str(estado) if estado else ESTADO_NO_ENCONTRADO,
                    "bases": str(bases) if bases else "",
                    "fecha": str(fecha) if fecha else "",
                }
            wb.close()
        except Exception as e:
            self._logger.warning(
                f"No se pudo leer el histórico previo de empresas no encontradas ({log_path}): {e}",
                user_msg=(
                    f"No se pudo leer el histórico previo de {log_path.name}; "
                    "el log de esta corrida solo tendrá los NITs pendientes de esta ejecución."
                ),
            )
        return previos

    def generate(self, resultados: list[NitResult], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME

        historial = self._read_previous(log_path)
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in resultados:
            nit = str(r.nit)
            if r.is_company and r.checked_bases == "Odoo, RUES":
                historial[nit] = {
                    "empresa": r.name or "",
                    "estado": ESTADO_FALTA_ODOO,
                    "bases": r.checked_bases,
                    "fecha": hora,
                }
            elif not r.is_company:
                historial[nit] = {
                    "empresa": r.name or "",
                    "estado": ESTADO_NO_ENCONTRADO,
                    "bases": r.checked_bases,
                    "fecha": hora,
                }
            else:
                historial.pop(nit, None)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "No Encontradas"

        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER

        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 48
        ws.column_dimensions["D"].width = 30
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 20
        ws.freeze_panes = "A2"

        falta_odoo_count = 0
        for i, (nit, data) in enumerate(sorted(historial.items()), 1):
            fila = i + 1
            estado = data.get("estado", ESTADO_NO_ENCONTRADO)
            if estado == ESTADO_FALTA_ODOO:
                falta_odoo_count += 1
            ws.append([i, nit, data["empresa"], estado, data["bases"], data["fecha"]])
            fill = _FILL_FALTA_ODOO if estado == ESTADO_FALTA_ODOO else _FILL_NO_ENCONTRADO
            for col in range(1, 7):
                cell = ws.cell(fila, col)
                cell.fill = fill
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER

        ws.append([])
        fila = ws.max_row + 1
        ws.cell(fila, 3, "TOTAL PENDIENTES").font = Font(
            bold=True, name="Arial", color="3D2B6B"
        )
        ws.cell(fila, 4, len(historial)).font = Font(
            bold=True, name="Arial", color="3D2B6B"
        )

        wb.save(log_path)
        self._logger.info(
            f"Log de empresas no encontradas guardado: {log_path} "
            f"({len(historial)} pendientes, {falta_odoo_count} solo faltan en Odoo)",
            user_msg=(
                f"{len(historial)} empresa(s) pendientes de verificación manual "
                f"({falta_odoo_count} existen en RUES pero faltan en Odoo); "
                f"revisa {log_path.name}."
            ),
        )
        return log_path
