from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.company.domain.entities.duplicate_candidate import DuplicateCandidate

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = ["#", "NIT A", "Empresa A", "NIT B", "Empresa B", "Motivo", "Similitud", "Fecha/Hora"]
_FILL_CANDIDATO = PatternFill("solid", fgColor="FFEB9C")
_SEPARADOR_MOTIVO = " | "


class DuplicateCompaniesLogGenerator:
    """Genera logs/empresas_duplicadas.xlsx: candidatos a empresa duplicada
    para revisión manual (principio 'VERIFICAR, nunca crear'). A diferencia
    de empresas_no_encontradas.xlsx, NO se fusiona con la corrida anterior:
    cada ejecución es un barrido completo de `companies`, así que el reporte
    ya refleja el estado real y un duplicado corregido desaparece solo."""

    FILENAME = "empresas_duplicadas.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def generate(self, candidates: list[DuplicateCandidate], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Duplicadas"

        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER

        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 48
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 48
        ws.column_dimensions["F"].width = 55
        ws.column_dimensions["G"].width = 12
        ws.column_dimensions["H"].width = 20
        ws.freeze_panes = "A2"

        for i, candidate in enumerate(candidates, 1):
            fila = i + 1
            estado = _SEPARADOR_MOTIVO.join(candidate.reasons)
            ws.append([
                i, candidate.nit_a, candidate.name_a, candidate.nit_b,
                candidate.name_b, estado, candidate.similarity, hora,
            ])
            for col in range(1, 9):
                cell = ws.cell(fila, col)
                cell.fill = _FILL_CANDIDATO
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER

        if candidates:
            ws.append([])
            fila = ws.max_row + 1
            ws.cell(fila, 3, "TOTAL CANDIDATOS").font = Font(
                bold=True, name="Arial", color="3D2B6B"
            )
            ws.cell(fila, 4, len(candidates)).font = Font(
                bold=True, name="Arial", color="3D2B6B"
            )

        wb.save(log_path)
        self._logger.info(
            f"Detección de duplicados guardada: {log_path} ({len(candidates)} candidato(s))",
            user_msg=(
                f"{len(candidates)} posible(s) empresa(s) duplicada(s); revisa {log_path.name}."
                if candidates
                else f"No se encontraron empresas duplicadas; revisa {log_path.name}."
            ),
        )
        return log_path
