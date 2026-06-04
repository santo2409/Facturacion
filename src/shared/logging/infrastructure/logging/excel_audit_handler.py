import atexit
import logging
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FILL_INFO = PatternFill("solid", fgColor="D6E4F0")
_FILL_WARNING = PatternFill("solid", fgColor="FFEB9C")
_FILL_ERROR = PatternFill("solid", fgColor="FFC7CE")


class ExcelAuditHandler(logging.Handler):
    """Handler that accumulates log records and writes them to an Excel file on close."""

    def __init__(self, filename="./logs/user_audit.xlsx", **kwargs):
        super().__init__()
        self._filename = filename
        self._records: list[dict] = []
        self._load_existing()
        atexit.register(self.flush_to_excel)

    def _load_existing(self):
        path = Path(self._filename)
        if not path.exists():
            return
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0]:
                    self._records.append({
                        "fecha": str(row[0]) if row[0] else "",
                        "nivel": str(row[1]) if len(row) > 1 and row[1] else "",
                        "mensaje": str(row[2]) if len(row) > 2 and row[2] else "",
                    })
            wb.close()
        except Exception:
            pass

    def emit(self, record):
        self._records.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "nivel": record.levelname,
            "mensaje": self.format(record) if self.formatter else record.getMessage(),
        })

    def flush_to_excel(self):
        if not self._records:
            return
        path = Path(self._filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Audit Log"

        headers = ["Fecha/Hora", "Nivel", "Mensaje"]
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center")
            c.border = _BORDER

        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 100
        ws.freeze_panes = "A2"

        for i, rec in enumerate(self._records, 2):
            ws.cell(i, 1, rec["fecha"]).border = _BORDER
            ws.cell(i, 2, rec["nivel"]).border = _BORDER
            ws.cell(i, 3, rec["mensaje"]).border = _BORDER

            fill = (
                _FILL_ERROR if rec["nivel"] in ("ERROR", "CRITICAL")
                else _FILL_WARNING if rec["nivel"] == "WARNING"
                else _FILL_INFO
            )
            for col in range(1, 4):
                ws.cell(i, col).fill = fill
                ws.cell(i, col).font = Font(name="Arial", size=9)

        wb.save(path)
