"""Genera logs/novedades_cups.xlsx: novedades de CUP detectadas al normalizar
(opción 3), corregidas o no, para revisión manual (principio "VERIFICAR, nunca
crear"). Calcado de DuplicateCompaniesLogGenerator: no se fusiona con la
corrida anterior, cada ejecución es un barrido completo. Ver
specs/005_correccion-cups-por-nombre/plan.md sección 3.6.
"""
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.dataProcessing.domain.entities.cup_novelty import (
    CupNovelty,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CRUCE_CUP_VALOR,
    ESTADO_HOMOLOGADO_BASE,
    ESTADO_NO_CORREGIDO_SUGERENCIA,
)

_THIN = Side(style="thin", color="CCCCCC")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADERS = [
    "#", "Hoja", "CUP original", "Examen", "CUP corregido",
    "Nombre en catálogo", "Estado", "Fase", "Filas afectadas",
    "Contratos (ejemplos)", "Fecha/Hora",
]

_FILL_CORREGIDO = PatternFill("solid", fgColor="C6E0B4")   # verde
_FILL_ATENCION = PatternFill("solid", fgColor="FFEB9C")    # ambar: swap y sugerencia
_FILL_NO_CORREGIDO = PatternFill("solid", fgColor="FFC7CE")  # rojo

_ESTADOS_CORREGIDOS = {
    ESTADO_CORREGIDO_NOMBRE,
    ESTADO_CORREGIDO_COOCURRENCIA,
    ESTADO_HOMOLOGADO_BASE,
}
_ESTADOS_ATENCION = {ESTADO_CRUCE_CUP_VALOR, ESTADO_NO_CORREGIDO_SUGERENCIA}

_SEPARADOR_CONTRATOS = ", "


def _fill_for(estado: str) -> PatternFill:
    if estado in _ESTADOS_CORREGIDOS:
        return _FILL_CORREGIDO
    if estado in _ESTADOS_ATENCION:
        return _FILL_ATENCION
    return _FILL_NO_CORREGIDO


def _sort_key(novelty: CupNovelty) -> tuple:
    """Orden de presentación: corregidas primero, luego sugerencias/cruces,
    luego sin resolver; dentro de cada bloque, por impacto (filas) descendente."""
    if novelty.estado in _ESTADOS_CORREGIDOS:
        bloque = 0
    elif novelty.estado in _ESTADOS_ATENCION:
        bloque = 1
    else:
        bloque = 2
    return (bloque, -novelty.filas)


class CupNoveltiesLogGenerator:
    FILENAME = "novedades_cups.xlsx"

    def __init__(self, logger):
        self._logger = logger

    def generate(self, novelties: list[CupNovelty], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / self.FILENAME
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Novedades"

        for col, h in enumerate(_HEADERS, 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
            c.fill = PatternFill("solid", fgColor="3D2B6B")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER

        widths = [5, 20, 14, 40, 14, 40, 32, 6, 14, 45, 20]
        for col, width in zip("ABCDEFGHIJK", widths):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"

        ordered = sorted(novelties, key=_sort_key)
        for i, novelty in enumerate(ordered, 1):
            fila = i + 1
            ws.append([
                i, novelty.hoja, novelty.cup_original, novelty.examen,
                novelty.cup_corregido or "", novelty.detalle, novelty.estado,
                novelty.fase, novelty.filas,
                _SEPARADOR_CONTRATOS.join(novelty.contratos), hora,
            ])
            fill = _fill_for(novelty.estado)
            for col in range(1, len(_HEADERS) + 1):
                cell = ws.cell(fila, col)
                cell.fill = fill
                cell.font = Font(name="Arial", size=10)
                cell.border = _BORDER

        if ordered:
            ws.append([])
            fila = ws.max_row + 1
            ws.cell(fila, 3, "TOTAL NOVEDADES").font = Font(bold=True, name="Arial", color="3D2B6B")
            ws.cell(fila, 4, len(ordered)).font = Font(bold=True, name="Arial", color="3D2B6B")

        wb.save(log_path)
        self._log_summary(ordered, log_path)
        return log_path

    def _log_summary(self, ordered: list[CupNovelty], log_path: Path):
        if not ordered:
            self._logger.info(
                f"No se detectaron novedades de CUP: {log_path}",
                user_msg="No se detectaron novedades de CUP.",
            )
            return

        # "Corregido" = se escribió un CUP nuevo (F0 swap, F1 nombre, F2
        # co-ocurrencia, F3 sufijo). F4 (sugerencia) y "no existe" NUNCA
        # escriben CUP (RF-05), así que van del lado de "no corregidos".
        corregidos = [n for n in ordered if n.cup_corregido is not None]
        no_corregidos = [n for n in ordered if n.cup_corregido is None]

        if corregidos:
            filas_corregidas = sum(n.filas for n in corregidos)
            detalle = [
                f"  '{n.cup_original}' -> '{n.cup_corregido}' ({n.estado}, {n.fase}, {n.filas} fila(s))"
                for n in corregidos
            ]
            self._logger.warning(
                f"{filas_corregidas} fila(s) con CUP corregido ({len(corregidos)} novedad(es)); revisa {log_path.name}:\n"
                + "\n".join(detalle[:50]),
                user_msg=f"Se corrigieron {filas_corregidas} fila(s) con CUP inválido; revisa {log_path.name}.",
            )

        if no_corregidos:
            filas_no_corregidas = sum(n.filas for n in no_corregidos)
            self._logger.error(
                f"{filas_no_corregidas} fila(s) con CUP sin corregir ({len(no_corregidos)} novedad(es)); revisa {log_path.name}",
                user_msg=f"{filas_no_corregidas} fila(s) con CUP no se pudieron corregir; revisa {log_path.name}.",
            )
