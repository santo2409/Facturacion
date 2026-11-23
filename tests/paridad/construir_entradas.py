"""Construye las entradas congeladas de la paridad ETL en `tests/paridad/entradas/prefacturas/`.

Todo es ficticio (no hay pre-facturas reales: traen datos de pacientes):
  1. Las pre-facturas que produce la opción 7 **real** de Facturacion a partir de las
     entradas del golden master (`tests/golden/entradas/opcion7_prefacturas/`).
     Se aplanan en una sola carpeta, como el ETL espera `datos/Entrada/`.
  2. Casos dirigidos (`pre_factura_9010000NN_*.xlsx`) con la misma plantilla de la
     opción 7, para recorrer las ramas del ETL que el golden no toca.

No sobrescribe: si la carpeta ya existe, se detiene. `--forzar` la regenera
(solo con un cambio aprobado: cambia las salidas de referencia).

Uso (venv de Facturacion):  python tests/paridad/construir_entradas.py [--forzar]
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import openpyxl  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402

from src.preInvoice.application.use_cases.split_by_nit import FIXED_COLUMNS  # noqa: E402
from tests.golden import _arnes  # noqa: E402

DESTINO = Path(__file__).resolve().parent / "entradas" / "prefacturas"

NOMBRES_EXAMEN = {
    "890201": "CONSULTA MEDICINA GENERAL",
    "890202": "CONSULTA ESPECIALISTA",
    "100006": "EXAMEN GRAVADO",
    "999999": "EXAMEN SIN PRODUCTO EN ODOO",
}


def _fila(**valores) -> dict:
    base = {
        "Base": "IMEDICAL OCTUBRE 1-20", "Ingreso N°": "1", "Sede": "SEDE NORTE",
        "Ciudad": "MEDELLIN", "FACTURADOR": "GENERAL", "Especial / General": "GENERAL",
        "Empresa Misión": None, "Medio de Pago": "CREDITO", "Fecha Ingreso": "05/10/2026",
        "Tipo Examen": "INGRESO", "Cargo": "OPERARIO",
    }
    base.update(valores)
    return base


def _escribir(nombre: str, filas: list[dict], codigos: list[str], quitar: str | None = None) -> None:
    """Misma disposición que la opción 7: fila 1 nombres de examen, fila 2 encabezados, datos desde la 3."""
    fijas = [c for c in FIXED_COLUMNS if c != quitar]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BASE GENERAL"
    ws.append([None] * len(fijas) + [NOMBRES_EXAMEN[c] for c in codigos])
    ws.append(fijas + codigos)
    for f in filas:
        ws.append([f.get(c) for c in fijas] + [f.get(c) for c in codigos])
    wb.save(DESTINO / nombre)


def _casos_dirigidos() -> None:
    sedes = dict(NIT="901000001", Empresa="CASOS SEDES SAS")
    _escribir("pre_factura_901000001_CASOS SEDES SAS.xlsx", [
        _fila(**sedes, Paciente="P01 SEDE103", **{"N° Identificación": "2001"}, Ciudad="BOGOTA D.C.", Sede="SEDE 103", **{"890201": 30000}),
        _fila(**sedes, Paciente="P02 ZONAIND", **{"N° Identificación": "2002"}, Ciudad="BOGOTA D.C.", Sede="ZONA INDUSTRIAL", **{"890201": 30000}),
        _fila(**sedes, Paciente="P03 SEDE103 EN CALI", **{"N° Identificación": "2003"}, Ciudad="CALI", Sede="SEDE 103", **{"890201": 30000}),
        _fila(**sedes, Paciente="P04 EXTRA BOGOTA", **{"N° Identificación": "2004"}, Ciudad="BOGOTA", Sede="EXTRAMURAL SERVICIO A DOMICILIO", **{"890202": 45000}),
        _fila(**sedes, Paciente="P05 MARIQUITA", **{"N° Identificación": "2005"}, Ciudad="Mariquita", **{"890201": 30000}),
        _fila(**sedes, Paciente="P06 TABIO", **{"N° Identificación": "2006"}, Ciudad="TABIO", **{"890201": 30000}),
        _fila(**sedes, Paciente="P07 PUEBLO", **{"N° Identificación": "2007"}, Ciudad="PUEBLO INVENTADO", **{"890201": 30000}),
        _fila(**sedes, Paciente="P08 BARRANQUILLA", **{"N° Identificación": "2008"}, Ciudad="BARRANQUILLA", **{"890201": 30000}),
        _fila(**sedes, Paciente="P09 GRAVADO", **{"N° Identificación": "2009"}, **{"100006": 15000, "999999": "$12,500"}),
        _fila(**sedes, Paciente="P10 BUGA", **{"N° Identificación": "2010"}, Ciudad="GUADALAJARA DE BUGA", **{"890201": 30000}),
        _fila(**sedes, Paciente="P11 DOBLE", **{"N° Identificación": "2011", "Ingreso N°": "7"}, **{"890201": 30000}),
        _fila(**sedes, Paciente="P11 DOBLE", **{"N° Identificación": "2011", "Ingreso N°": "7"}, **{"890201": 30000, "890202": 45000}),
        _fila(**sedes, Paciente="P12 EXTRA MEDELLIN", **{"N° Identificación": "2012"}, Sede="EXTRAMURAL", **{"890201": 30000}),
        _fila(**sedes, Paciente="P13 SEPTIEMBRE", **{"N° Identificación": "2013"}, Base="IMEDICAL SEPTIEMBRE 21-30", **{"890201": 0}),
        _fila(NIT=None, Empresa="CASOS SEDES SAS", Paciente="P14 SIN NIT", **{"N° Identificación": "2014"}, **{"890201": 30000}),
    ], ["890201", "890202", "100006", "999999"])

    def una(nit, empresa, **extra):
        return [_fila(NIT=nit, Empresa=empresa, Paciente="PACIENTE " + nit, **{"N° Identificación": "3" + nit[-3:]},
                      **{"890201": 30000}, **extra)]

    _escribir("pre_factura_900448167_NIT BLOQUEADO PRUEBA.xlsx", una("900448167", "NIT BLOQUEADO PRUEBA"), ["890201"])
    _escribir("pre_factura_901000002_SGS COLOMIA PRUEBA.xlsx", una("901000002", "SGS COLOMIA PRUEBA SAS"), ["890201"])
    _escribir("pre_factura_901000003_TERCERO DUPLICADO.xlsx", una("901000003", "TERCERO DUPLICADO SAS"), ["890201"])
    _escribir("pre_factura_901000004_NOMBRE DISTINTO.xlsx", una("901000004", "NOMBRE DISTINTO SAS"), ["890201"])
    _escribir("pre_factura_901000005_PLANTILLA SIN NIT.xlsx", una("901000005", "PLANTILLA SIN NIT SAS"), ["890201"], quitar="NIT")
    _escribir("pre_factura_901000006_SIN LINEAS.xlsx", una("901000006", "SIN LINEAS SAS", Ciudad="PUEBLO INVENTADO"), ["890201"])
    _escribir("pre_factura_12345_NIT CORTO.xlsx", una("12345", "NIT CORTO SAS"), ["890201"])
    _escribir("pre_factura_900111111_EMPRESA ALFA SAS (segundo archivo).xlsx",
              una("900111111", "EMPRESA ALFA SAS", Ciudad="MEDELLIN"), ["890201"])


def _desde_opcion7() -> None:
    with tempfile.TemporaryDirectory(prefix="paridad_op7_") as tmp, MonkeyPatch.context() as mp:
        trabajo = Path(tmp) / "trabajo"
        _arnes.ejecutar("opcion7_prefacturas", trabajo, mp)
        for ruta in sorted((trabajo / "pre-facturas").rglob("*.xlsx")):
            nombre = ruta.name
            if (DESTINO / nombre).exists():  # mismo NIT en dos carpetas de facturador
                nombre = f"{ruta.stem} ({ruta.parent.name}){ruta.suffix}"
            shutil.copy2(ruta, DESTINO / nombre)


def main() -> int:
    if DESTINO.exists():
        if "--forzar" not in sys.argv:
            print(f"{DESTINO} ya existe; no se sobrescribe (usar --forzar con cambio aprobado).")
            return 1
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)
    _desde_opcion7()
    _casos_dirigidos()
    for p in sorted(DESTINO.iterdir()):
        print(p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
