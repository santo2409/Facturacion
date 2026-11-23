from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = [
    "#", "Etiqueta", "NIT Original", "Empresa Original", "NIT Destino", "Empresa Facturada", "Registros",
]
_WIDTHS = {"A": 5, "B": 14, "C": 16, "D": 45, "E": 16, "F": 45, "G": 12}


class RedirectedCompaniesLogGenerator:
    """Genera logs/empresas_redirigidas.xlsx: empresas que en esta corrida se
    facturan bajo otro NIT según la tabla `billing_redirects`.

    Como empresas_tian.xlsx, no se fusiona con corridas anteriores: refleja solo
    lo que se redirigió en esta corrida. Solo se llama si hubo redirecciones.
    """

    FILENAME = "empresas_redirigidas.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def generate(self, rows: list, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Empresas Redirigidas"

        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER
        for letra, ancho in _WIDTHS.items():
            ws.column_dimensions[letra].width = ancho
        ws.freeze_panes = "A2"

        total_registros = 0
        for i, a in enumerate(rows, 1):
            ws.append([i, a.etiqueta, a.nit_original, a.name_original, a.nit_destino, a.name_final, a.rows])
            for col in range(1, len(_HEADERS) + 1):
                cell = ws.cell(i + 1, col)
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER
            total_registros += a.rows

        fila = ws.max_row + 2
        ws.cell(fila, 4, "TOTAL").font = Font(bold=True, name="Arial", color="3D2B6B")
        ws.cell(fila, 6, len(rows)).font = Font(bold=True, name="Arial", color="3D2B6B")
        ws.cell(fila, 7, total_registros).font = Font(bold=True, name="Arial", color="3D2B6B")

        wb.save(log_path)
        self._logger.info(
            f"Reporte de redirecciones generado: {len(rows)} empresa(s), {total_registros} registro(s) → {log_path}",
            user_msg=(
                f"{len(rows)} empresa(s) se facturarán bajo otro NIT en esta corrida; "
                f"revisa {self.FILENAME}."
            ),
        )
        return log_path
