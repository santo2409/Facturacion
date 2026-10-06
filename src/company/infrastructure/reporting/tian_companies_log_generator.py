from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = ["#", "NIT Original", "Empresa Original", "NIT TIAN", "Empresa Facturada", "Registros"]


class TianCompaniesLogGenerator:
    """Genera logs/empresas_tian.xlsx: empresas redirigidas a facturarse bajo el
    NIT de TIAN en la corrida actual (spec 008, RF-20).

    A diferencia de NotFoundCompaniesLogGenerator, este libro NO se fusiona con
    corridas anteriores: refleja "qué se redirigió en esta corrida", y arrastrar
    historia daría un listado engañoso de quién se factura a TIAN este mes.
    """

    FILENAME = "empresas_tian.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def generate(self, rows: list, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Empresas TIAN"

        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER

        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 45
        ws.column_dimensions["D"].width = 16
        ws.column_dimensions["E"].width = 45
        ws.column_dimensions["F"].width = 12
        ws.freeze_panes = "A2"

        total_registros = 0
        for i, a in enumerate(rows, 1):
            ws.append([i, a.nit_original, a.name_original, a.nit_tian, a.name_final, a.rows])
            for col in range(1, 7):
                cell = ws.cell(i + 1, col)
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER
            total_registros += a.rows

        fila = ws.max_row + 2
        ws.cell(fila, 3, "TOTAL").font = Font(bold=True, name="Arial", color="3D2B6B")
        ws.cell(fila, 5, len(rows)).font = Font(bold=True, name="Arial", color="3D2B6B")
        ws.cell(fila, 6, total_registros).font = Font(bold=True, name="Arial", color="3D2B6B")

        wb.save(log_path)
        self._logger.info(
            f"Reporte TIAN generado: {len(rows)} empresa(s), {total_registros} registro(s) → {log_path}",
            user_msg=(
                f"{len(rows)} empresa(s) se facturarán a TIAN en esta corrida; "
                f"revisa {self.FILENAME}."
            ),
        )
        return log_path
