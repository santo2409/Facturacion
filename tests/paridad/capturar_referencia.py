"""Ejecuta ETL-Avancys (`Pipeline.py`, sin cambios) contra un Odoo simulado y exporta sus salidas.

Destino: SOLO el Odoo simulado en memoria (`tests/golden/_odoo_simulado.py` + `entradas/odoo.json`).
Cada corrida parte de un simulador nuevo (destino reiniciado). Salvaguardas, en este orden:
  - `ODOO_URL/DB/USER/API_KEY` se fijan a valores ficticios (`*.invalid`); el ETL lee el entorno
    antes que el `.env` (`os.environ.setdefault`, Pipeline.py:69) y además se exige que no haya
    ningún `.env` en las carpetas padre de la copia.
  - `xmlrpc.client.ServerProxy` se sustituye por el simulador ANTES de ejecutar el script.
  - Cualquier conexión de red (socket) lanza error: si algo intentara salir, la corrida falla.
  - Se ejecuta una COPIA de Pipeline.py en una carpeta temporal fija: ETL-Avancys no se escribe.

Debe correr con el intérprete del ETL (pandas 3.0.5, rapidfuzz 3.14.6), con -B para no escribir .pyc:
    /home/santiagosoa/Desarrollo/ETL-Avancys/venv/bin/python -B tests/paridad/capturar_referencia.py /tmp/etl_run1

Exporta en la carpeta de salida (ver LEEME.md):
  odoo_escrituras.json   create/write enviados a Odoo, por NIT
  salida/*.json          cada libro .xlsx volcado a JSON (valores por hoja)
  salida/facturas_creadas.csv, salida/log_inyeccion.txt, salida/verificar.json
Sin normalizar: la normalización la aplica `normalizar.py`.
"""

from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import socket
import sys
import tempfile
import xmlrpc.client
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_FACTURACION = AQUI.parents[1]
ETL = Path("/home/santiagosoa/Desarrollo/ETL-Avancys/Pipeline.py")
ENTRADAS = AQUI / "entradas"
TRABAJO = Path(tempfile.gettempdir()) / "etl_paridad_trabajo"  # fija: la ruta sale en el log

ENTORNO_SIMULADO = {
    "ODOO_URL": "http://odoo.simulado.invalid",
    "ODOO_DB": "simulada",
    "ODOO_USER": "paridad",
    "ODOO_API_KEY": "no-es-una-clave",
}


def _cargar_simulador():
    spec = importlib.util.spec_from_file_location("_odoo_simulado", RAIZ_FACTURACION / "tests/golden/_odoo_simulado.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sim = _cargar_simulador()


class OdooParidad(_sim.OdooSimulado):
    """El simulador del golden + `write` y facturas creadas visibles para la guarda anti-duplicados."""

    def __init__(self, datos):
        super().__init__(datos)
        self.escrituras: list[dict] = []

    def execute_kw(self, db, uid, key, model, method, args=None, kwargs=None):
        if method == "write":
            ids, vals = args
            self.escrituras.append({"metodo": "write", "modelo": model, "ids": list(ids), "vals": copy.deepcopy(vals)})
            for rid in ids:
                registro = self._por_id(model, rid)
                if registro is not None:
                    registro.update(vals)
            return True
        return super().execute_kw(db, uid, key, model, method, args, kwargs)

    def _create(self, model, vals):
        rid = super()._create(model, vals)
        self.escrituras.append({"metodo": "create", "modelo": model, "id": rid, "vals": copy.deepcopy(vals)})
        registro = dict(copy.deepcopy(vals), id=rid, create_uid=self.uid,
                        create_date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        self._datos.setdefault(model, []).append(registro)
        return rid


def _bloquear_red():
    def _prohibido(*_a, **_k):
        raise RuntimeError("paridad: conexión de red bloqueada (solo Odoo simulado)")
    socket.socket.connect = _prohibido
    socket.create_connection = _prohibido


def _preparar_trabajo() -> Path:
    if TRABAJO.exists():
        shutil.rmtree(TRABAJO)
    entrada = TRABAJO / "datos" / "Entrada"
    entrada.mkdir(parents=True)
    for p in sorted((ENTRADAS / "prefacturas").iterdir()):
        shutil.copy2(p, entrada / p.name)
    copia = TRABAJO / "Pipeline.py"
    shutil.copy2(ETL, copia)
    envs = [c / ".env" for c in copia.parents if (c / ".env").exists()]
    if envs:
        raise SystemExit(f"paridad: hay un .env en {envs[0].parent}; el ETL lo leería. Abortado.")
    return copia


def _celda(v):
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    return v


def _xlsx_a_json(ruta: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(ruta)
    libro = {}
    for ws in wb.worksheets:
        libro[ws.title] = {
            "filas": [[_celda(c.value) for c in fila] for fila in ws.iter_rows()],
            "hipervinculos": {c.coordinate: c.hyperlink.target for fila in ws.iter_rows() for c in fila if c.hyperlink},
        }
    return libro


def _escribir_json(ruta: Path, obj) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _exportar(odoo: OdooParidad, salida: Path) -> None:
    # Escrituras ordenadas por clave estable: NIT del tercero (ref_num) y luego orden de llamada.
    nit_de = {p["id"]: p.get("ref_num") for p in odoo._datos.get("res.partner", [])}
    partner_de_factura = {e["id"]: e["vals"].get("partner_id") for e in odoo.escrituras if e["metodo"] == "create"}
    escrituras = []
    for orden, e in enumerate(odoo.escrituras):
        fid = e["id"] if e["metodo"] == "create" else e["ids"][0]
        escrituras.append({"nit": str(nit_de.get(partner_de_factura.get(fid))), "orden_llamada": orden, **e})
    escrituras.sort(key=lambda e: (e["nit"], e["orden_llamada"]))
    _escribir_json(salida / "odoo_escrituras.json", escrituras)

    origen = TRABAJO / "datos" / "Salida"
    destino = salida / "salida"
    destino.mkdir()
    for p in sorted(origen.iterdir()):
        if p.suffix == ".xlsx":
            _escribir_json(destino / (p.name + ".json"), _xlsx_a_json(p))
        elif p.is_file():
            shutil.copy2(p, destino / p.name)
    verificar = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                 for p in sorted((origen / "verificar").iterdir())}
    _escribir_json(destino / "verificar.json", verificar)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    salida = Path(sys.argv[1]).resolve()
    if salida.exists() and any(salida.iterdir()):
        raise SystemExit(f"paridad: {salida} no está vacía.")
    salida.mkdir(parents=True, exist_ok=True)

    for clave in [k for k in os.environ if k.startswith("ODOO")]:
        del os.environ[clave]
    os.environ.update(ENTORNO_SIMULADO)

    copia = _preparar_trabajo()
    odoo = OdooParidad(json.loads((ENTRADAS / "odoo.json").read_text(encoding="utf-8")))
    xmlrpc.client.ServerProxy = _sim.ServerProxySimulado(odoo)
    _bloquear_red()

    os.chdir(TRABAJO)
    try:
        runpy.run_path(str(copia), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise
    _exportar(odoo, salida)
    print(f"paridad: {len(odoo.escrituras)} escrituras; salidas en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
