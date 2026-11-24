"""Compara XlsxPreInvoiceSource con la lectura de ETL-Avancys (pandas) sobre una carpeta.

Solo lectura. No imprime datos de pacientes: solo nombres de archivo y conteos.
Debe correr con el intérprete del ETL (tiene pandas) desde la raíz de Facturacion:
    /home/santiagosoa/Desarrollo/ETL-Avancys/venv/bin/python -B tests/paridad/verificar_lector.py <carpeta>
"""

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.odooInjection.infrastructure.persistence.xlsx_pre_invoice_source import (  # noqa: E402
    leer_hoja_como_pandas,
)


def _pandas(ruta):
    df = pd.read_excel(ruta, header=None, dtype=str)
    return [[None if (isinstance(v, float) and math.isnan(v)) else v for v in fila]
            for fila in df.values.tolist()]


def main() -> int:
    carpeta = Path(sys.argv[1])
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".xlsx" and not p.name.startswith("~$"))
    distintos = 0
    for p in archivos:
        try:
            esperado = _pandas(p)
        except Exception as e:  # noqa: BLE001
            esperado = f"{type(e).__name__}: {e}"
        try:
            obtenido = leer_hoja_como_pandas(p)
        except Exception as e:  # noqa: BLE001
            obtenido = f"{type(e).__name__}: {e}"
        if esperado != obtenido:
            distintos += 1
            print("DISTINTO:", p.name)
    print(f"{len(archivos)} archivos, {distintos} distintos")
    return 1 if distintos else 0


if __name__ == "__main__":
    sys.exit(main())
