from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.company.domain.entities.unlinked_row import UnlinkedRow

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = ["#", "Documento", "Razón Social", "Paquete", "Motivo", "Fecha/Hora"]
_FILL_FILA = PatternFill("solid", fgColor="FFEB9C")


class NotLinkedCompaniesLogGenerator:
    """Genera logs/empresas_no_vinculadas.xlsx: filas del Excel de la opción 5
    cuya empresa no existe en `companies` (principio 'VERIFICAR, nunca crear').
    Igual que DuplicateCompaniesLogGenerator, cada ejecución es un barrido
    completo: no se fusiona con la corrida anterior."""

    FILENAME = "empresas_no_vinculadas.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def generate(self, rows: list[UnlinkedRow], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "No Vinculadas"

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
        ws.column_dimensions["E"].width = 48
        ws.column_dimensions["F"].width = 20
        ws.freeze_panes = "A2"

        for i, row in enumerate(rows, 1):
            fila = i + 1
            ws.append([i, row.document, row.company_name, row.package, row.reason, hora])
            for col in range(1, 7):
                cell = ws.cell(fila, col)
                cell.fill = _FILL_FILA
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER

        if rows:
            ws.append([])
            fila = ws.max_row + 1
            ws.cell(fila, 3, "TOTAL NO VINCULADAS").font = Font(
                bold=True, name="Arial", color="3D2B6B"
            )
            ws.cell(fila, 4, len(rows)).font = Font(
                bold=True, name="Arial", color="3D2B6B"
            )

        wb.save(log_path)
        self._logger.info(
            f"Empresas no vinculadas guardadas: {log_path} ({len(rows)} fila(s))",
            user_msg=(
                f"{len(rows)} fila(s) no se pudieron vincular a una empresa; revisa {log_path.name}."
                if rows
                else f"Todas las filas se vincularon correctamente; revisa {log_path.name}."
            ),
        )
        return log_path
