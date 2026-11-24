"""Excel de configuración de la carga de pre-facturas (E-04).

Hojas y columnas (fila 1 = encabezados):
  NITS_BLOQUEADOS      NIT | MOTIVO
  EMPRESAS_BLOQUEADAS  NOMBRE | MOTIVO
  YA_SUBIDAS           NIT | FACTURA
Una hoja vacía es válida. Las filas sin NIT/NOMBRE se ignoran.
"""

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from src.odooInjection.domain.entities.injection_settings import InjectionSettings
from src.odooInjection.domain.repositories.injection_settings_source import (
    InjectionSettingsSource,
)

HOJAS = {
    "NITS_BLOQUEADOS": ("NIT", "MOTIVO"),
    "EMPRESAS_BLOQUEADAS": ("NOMBRE", "MOTIVO"),
    "YA_SUBIDAS": ("NIT", "FACTURA"),
}

_NOTAS = {
    "NITS_BLOQUEADOS": "El NIT existe en Odoo pero apunta a otro tercero: no se factura (VERIFICAR) hasta resolverlo.",
    "EMPRESAS_BLOQUEADAS": "Se compara sin tildes y en mayúsculas; basta con que el nombre EMPIECE así.",
    "YA_SUBIDAS": "VACIAR CADA MES. Solo para repetir una corrida cortada del MISMO lote: NIT y id de la factura ya creada.",
}


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _factura(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return v


class XlsxInjectionSettingsSource(InjectionSettingsSource):
    def exists(self, path: Path) -> bool:
        return Path(path).is_file()

    def read(self, path: Path) -> InjectionSettings:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            datos = {}
            for hoja, columnas in HOJAS.items():
                if hoja not in wb.sheetnames:
                    raise ValueError(f"Al archivo {Path(path).name} le falta la hoja '{hoja}'.")
                filas = list(wb[hoja].iter_rows(values_only=True))
                encabezado = [_texto(c).upper() for c in (filas[0] if filas else ())]
                faltan = [c for c in columnas if c not in encabezado]
                if faltan:
                    raise ValueError(
                        f"La hoja '{hoja}' de {Path(path).name} debe tener las columnas "
                        f"{', '.join(columnas)} en la fila 1 (falta {', '.join(faltan)}).")
                i_clave, i_valor = (encabezado.index(c) for c in columnas)
                valores = {}
                for fila in filas[1:]:
                    clave = _texto(fila[i_clave] if i_clave < len(fila) else None)
                    if not clave:
                        continue
                    valor = fila[i_valor] if i_valor < len(fila) else None
                    valores[clave] = _factura(valor) if hoja == "YA_SUBIDAS" else _texto(valor)
                datos[hoja] = valores
        finally:
            wb.close()
        return InjectionSettings(
            nits_bloqueados=datos["NITS_BLOQUEADOS"],
            empresas_bloqueadas=datos["EMPRESAS_BLOQUEADAS"],
            ya_subidas=datos["YA_SUBIDAS"],
        )

    def create(self, path: Path, settings: InjectionSettings) -> None:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        contenido = {
            "NITS_BLOQUEADOS": settings.nits_bloqueados,
            "EMPRESAS_BLOQUEADAS": settings.empresas_bloqueadas,
            "YA_SUBIDAS": settings.ya_subidas,
        }
        for hoja, columnas in HOJAS.items():
            ws = wb.create_sheet(hoja)
            ws.append(list(columnas))
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
                c.fill = PatternFill("solid", fgColor="3D2B6B")
            for clave, valor in contenido[hoja].items():
                ws.append([clave, valor])
                ws.cell(ws.max_row, 1).number_format = "@"
            ws.column_dimensions["A"].width = 30
            ws.column_dimensions["B"].width = 90
            ws.column_dimensions["D"].width = 90
            nota = ws.cell(1, 4, _NOTAS[hoja])
            nota.font = Font(italic=True, name="Arial", size=9, color="8A4B00")
            nota.alignment = Alignment(wrap_text=True, vertical="top")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
