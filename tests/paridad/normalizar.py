"""Normaliza, EN SITIO, una carpeta exportada por `capturar_referencia.py`.

Solo toca los campos que variaron entre dos corridas idénticas (ver LEEME.md, "Normalizaciones"):
  N1  salida/log_inyeccion.txt: el prefijo `AAAA-MM-DD HH:MM:SS |` de cada línea (asctime del logging).
  N2  salida/log_inyeccion.xlsx.json: la columna `Fecha/Hora` de la hoja `Log Inyeccion`.
Ambos se reemplazan por `<FECHA_HORA>`. Nada más se modifica.

Uso:  python tests/paridad/normalizar.py /tmp/etl_run1
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARCA = "<FECHA_HORA>"
_FECHA_HORA = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


def _n1_log_texto(ruta: Path) -> int:
    texto = ruta.read_text(encoding="utf-8")
    nuevo, n = re.subn(rf"^{_FECHA_HORA} \|", f"{MARCA} |", texto, flags=re.MULTILINE)
    ruta.write_text(nuevo, encoding="utf-8")
    return n


def _n2_log_excel(ruta: Path) -> int:
    libro = json.loads(ruta.read_text(encoding="utf-8"))
    filas = libro["Log Inyeccion"]["filas"]
    encabezado = next(i for i, f in enumerate(filas) if "Fecha/Hora" in f)
    col = filas[encabezado].index("Fecha/Hora")
    n = 0
    for fila in filas[encabezado + 1:]:
        if len(fila) > col and isinstance(fila[col], str) and re.fullmatch(_FECHA_HORA, fila[col]):
            fila[col] = MARCA
            n += 1
    ruta.write_text(json.dumps(libro, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return n


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    carpeta = Path(sys.argv[1])
    n1 = _n1_log_texto(carpeta / "salida" / "log_inyeccion.txt")
    n2 = _n2_log_excel(carpeta / "salida" / "log_inyeccion.xlsx.json")
    print(f"normalizado {carpeta}: N1={n1} líneas de log, N2={n2} celdas Fecha/Hora")
    return 0


if __name__ == "__main__":
    sys.exit(main())
