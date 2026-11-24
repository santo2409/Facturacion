"""Paridad de la opción 5 (Cargar Pre Facturas) con ETL-Avancys.

Ejecuta el caso de uso real (`LoadPreInvoicesToOdoo` con sus adaptadores reales:
lector, `XmlRpcOdooRepository` + gateway, libros) sobre `entradas/prefacturas/` contra el
mismo Odoo simulado con el que se capturó el ETL (`capturar_referencia.OdooParidad`),
exporta igual que la captura, normaliza (N2) y compara con `esperado/`:
  - odoo_escrituras.json (cada create y write enviados a Odoo): igual exacto;
  - log_inyeccion / pendientes_facturador / cuentas_por_revisar (.xlsx → JSON) y
    facturas_creadas.csv: igual exacto;
  - verificar/: mismos archivos, copiados sin cambios.
`log_inyeccion.txt` no se compara: el log técnico va a logs.log (diseno-integracion.md).
"""

import hashlib
import json
import os
import shutil
import socket
import sys
import xmlrpc.client
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import capturar_referencia as captura  # noqa: E402
import normalizar  # noqa: E402

from src.odooInjection.application.use_cases.load_pre_invoices_to_odoo import (  # noqa: E402
    LoadPreInvoicesToOdoo,
)
from src.odooInjection.config import get_injection_config, get_odoo_config  # noqa: E402
from src.odooInjection.domain.entities.injection_settings import valores_del_etl  # noqa: E402
from src.odooInjection.infrastructure.odoo.xmlrpc_injection_gateway import (  # noqa: E402
    XmlRpcInjectionGateway,
)
from src.odooInjection.infrastructure.odoo.xmlrpc_odoo_repository import (  # noqa: E402
    XmlRpcOdooRepository,
)
from src.odooInjection.infrastructure.persistence.xlsx_pre_invoice_source import (  # noqa: E402
    XlsxPreInvoiceSource,
)
from src.odooInjection.infrastructure.reporting.etl_injection_report_writer import (  # noqa: E402
    EtlInjectionReportWriter,
)
from tests.fakes.fake_logger import FakeLogger  # noqa: E402

ESPERADO = Path(os.environ.get("PARIDAD_ESPERADO") or AQUI / "esperado")
PREFACTURAS = AQUI / "entradas" / "prefacturas"
LIBROS = ("log_inyeccion.xlsx", "pendientes_facturador.xlsx", "cuentas_por_revisar.xlsx")


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]


def _correr(tmp_path, monkeypatch) -> tuple[Path, captura.OdooParidad]:
    for clave in [k for k in os.environ if k.startswith(("ODOO", "INYECCION"))]:
        monkeypatch.delenv(clave)
    monkeypatch.setenv("ODOO_URL", captura.ENTORNO_SIMULADO["ODOO_URL"])
    monkeypatch.setenv("ODOO_DB", captura.ENTORNO_SIMULADO["ODOO_DB"])
    monkeypatch.setenv("ODOO_USERNAME", captura.ENTORNO_SIMULADO["ODOO_USER"])
    monkeypatch.setenv("ODOO_API_KEY", captura.ENTORNO_SIMULADO["ODOO_API_KEY"])

    odoo = captura.OdooParidad(json.loads((AQUI / "entradas" / "odoo.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(xmlrpc.client, "ServerProxy", captura._sim.ServerProxySimulado(odoo))

    def _prohibido(*_a, **_k):
        raise RuntimeError("paridad: conexión de red bloqueada")
    monkeypatch.setattr(socket.socket, "connect", _prohibido)
    monkeypatch.setattr(socket, "create_connection", _prohibido)

    odoo_cfg = get_odoo_config()
    cfg = {**odoo_cfg, **get_injection_config()}
    logger = FakeLogger()
    salida = tmp_path / "Salida"
    repo = XmlRpcOdooRepository(url=odoo_cfg["url"], db=odoo_cfg["db"], username=odoo_cfg["username"],
                                api_key=odoo_cfg["api_key"], logger=logger, config=odoo_cfg)
    LoadPreInvoicesToOdoo(
        gateway=XmlRpcInjectionGateway(repo, odoo_cfg["url"], odoo_cfg["db"], odoo_cfg["api_key"]),
        source=XlsxPreInvoiceSource(logger),
        settings=valores_del_etl(),
        writer=EtlInjectionReportWriter(salida, logger),
        logger=logger,
        config=cfg,
        sleep=lambda _s: None,
    ).execute(PREFACTURAS)
    return salida, odoo


def _exportar(odoo, salida: Path, destino: Path) -> None:
    """Mismo formato que capturar_referencia._exportar."""
    nit_de = {p["id"]: p.get("ref_num") for p in odoo._datos.get("res.partner", [])}
    partner_de_factura = {e["id"]: e["vals"].get("partner_id") for e in odoo.escrituras if e["metodo"] == "create"}
    escrituras = []
    for orden, e in enumerate(odoo.escrituras):
        fid = e["id"] if e["metodo"] == "create" else e["ids"][0]
        escrituras.append({"nit": str(nit_de.get(partner_de_factura.get(fid))), "orden_llamada": orden, **e})
    escrituras.sort(key=lambda e: (e["nit"], e["orden_llamada"]))
    destino.mkdir()
    captura._escribir_json(destino / "odoo_escrituras.json", escrituras)
    (destino / "salida").mkdir()
    for nombre in LIBROS:
        captura._escribir_json(destino / "salida" / (nombre + ".json"), captura._xlsx_a_json(salida / nombre))
    shutil.copy2(salida / "facturas_creadas.csv", destino / "salida" / "facturas_creadas.csv")
    normalizar._n2_log_excel(destino / "salida" / "log_inyeccion.xlsx.json")


@pytest.fixture(scope="module")
def obtenido(tmp_path_factory):
    if not ESPERADO.is_dir():
        pytest.fail(f"Falta {ESPERADO}: copiar la captura del ETL (ver tests/paridad/LEEME.md).")
    if not PREFACTURAS.is_dir():
        pytest.fail("Faltan las pre-facturas de entrada: python tests/paridad/construir_entradas.py")
    mp = pytest.MonkeyPatch()
    try:
        tmp = tmp_path_factory.mktemp("paridad")
        salida, odoo = _correr(tmp, mp)
        destino = tmp / "obtenido"
        _exportar(odoo, salida, destino)
        return destino, salida
    finally:
        mp.undo()


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def test_paridad_escrituras_a_odoo(obtenido):
    destino, _ = obtenido
    assert _leer(destino / "odoo_escrituras.json") == _leer(ESPERADO / "odoo_escrituras.json")


@pytest.mark.parametrize("libro", LIBROS)
def test_paridad_libros_de_salida(obtenido, libro):
    destino, _ = obtenido
    assert _leer(destino / "salida" / (libro + ".json")) == _leer(ESPERADO / "salida" / (libro + ".json"))


def test_paridad_facturas_creadas_csv(obtenido):
    destino, _ = obtenido
    assert _leer(destino / "salida" / "facturas_creadas.csv") == _leer(ESPERADO / "salida" / "facturas_creadas.csv")


def test_paridad_archivos_apartados_en_verificar(obtenido):
    _, salida = obtenido
    esperados = json.loads(_leer(ESPERADO / "salida" / "verificar.json"))
    copiados = sorted(p.name for p in (salida / "verificar").iterdir())
    assert copiados == sorted(esperados)
    for nombre in copiados:
        assert _sha(salida / "verificar" / nombre) == _sha(PREFACTURAS / nombre)
