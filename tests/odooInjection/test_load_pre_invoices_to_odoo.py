"""Reglas de la carga de pre-facturas (T8-T29 de docs/etl-analisis.md) con fakes."""
from datetime import datetime
from pathlib import Path

from src.odooInjection.application.use_cases.load_pre_invoices_to_odoo import LoadPreInvoicesToOdoo
from src.odooInjection.domain.entities.injection_settings import InjectionSettings
from tests.fakes.fake_injection_gateway import FakeInjectionGateway
from tests.fakes.fake_injection_report_writer import FakeInjectionReportWriter
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_pre_invoice_source import FakePreInvoiceSource

CONFIG = {
    "url": "http://odoo.test", "diario_id": 47, "cuenta_ingresos_excluidos": 42653,
    "cuenta_ingresos_gravados": 42650, "productos_gravados": ["100006"],
    "taxes": ["AUTORRETENCION IMPUESTO RENTA 2%", "AUTORRETENCION COMPRA IMPUESTO RENTA 2%"],
    "nombre_uom": "Unidades", "actualizar_precios": False,
}
CUENTA_CALI = {"id": 4, "code": "AA10405", "name": "SEDE SOA - PROVEEDORES - CALI"}
PRODUCTOS = [
    {"id": 601, "default_code": "890201", "name": "CONSULTA", "list_price": 1.0},
    {"id": 602, "default_code": "100006", "name": "GRAVADO", "list_price": 1.0},
]
TERCERO = {"id": 505, "name": "EMPRESA ALFA SAS", "ref_num": "900111111"}


def _fila(nit="900111111", empresa="EMPRESA ALFA SAS", ciudad="CALI", cedula="1", ingreso="10", **examenes):
    return {"NIT": nit, "Empresa": empresa, "Ciudad": ciudad, "Sede": "SEDE", "Paciente": "P" + cedula,
            "N Identificacion": cedula, "Ingreso": ingreso, "Base": "IMEDICAL OCTUBRE 1-20", **examenes}


def _correr(filas, cols=("890201", "100006"), gateway=None, settings=None, config=None, archivos=None, sleep=None):
    gateway = gateway or FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI],
                                              taxes={CONFIG["taxes"][0]: 701, CONFIG["taxes"][1]: 702},
                                              uoms={"Unidades": 1})
    writer = FakeInjectionReportWriter()
    logger = FakeLogger()
    uc = LoadPreInvoicesToOdoo(
        gateway=gateway,
        source=FakePreInvoiceSource(archivos if archivos is not None else {"a.xlsx": (filas, list(cols))}),
        settings=settings or InjectionSettings(),
        writer=writer, logger=logger, config={**CONFIG, **(config or {})},
        sleep=sleep or (lambda _s: None), now=lambda: datetime(2026, 11, 5, 10, 30),
    )
    resumen = uc.execute(Path("entrada"))
    return resumen, gateway, writer, uc, logger


def _detalle(writer, nit="900111111"):
    return next(r for r in writer.ultimos_resultados if r["nit"] == nit)


def test_t22_t24_t27_una_factura_con_lineas_ordenadas_y_sin_fechas():
    filas = [_fila(cedula="1", **{"890201": 1.0, "100006": 1.0}), _fila(cedula="2", **{"890201": 30000.0})]
    resumen, gateway, writer, _, _ = _correr(filas)
    assert resumen["ok"] == 1
    vals = gateway.creadas[0]["vals"]
    assert vals["narration"] == "Pre-factura automatica. Pacientes: 2"
    assert vals["journal_id"] == 47 and vals["state"] == "draft" and vals["move_type"] == "out_invoice"
    assert not {"invoice_date", "invoice_date_due", "date_of_service", "range_id"} & set(vals)
    lineas = [l[2] for l in vals["invoice_line_ids"]]
    assert [(l["product_id"], l["quantity"], l["account_id"]) for l in lineas] == [(602, 1, 42650), (601, 2, 42653)]
    assert lineas[0]["tax_ids"] == [(6, 0, [701, 702])] and lineas[0]["analytic_account_id"] == 4
    assert gateway.vencimientos_limpiados == [9001]                       # T28
    assert writer.creadas == [(9001, "900111111", "EMPRESA ALFA SAS", "http://odoo.test/web#id=9001&model=account.move&view_type=form")]


def test_t16_sin_tercero_nit_invalido_y_varios_terceros_van_a_verificar():
    gateway = FakeInjectionGateway(partners=[{"id": 1, "name": "A", "ref_num": "901000003"},
                                             {"id": 2, "name": "B", "ref_num": "901000003"}],
                                   products=PRODUCTOS, accounts=[CUENTA_CALI])
    filas = [_fila(nit="555555555", **{"890201": 1.0}), _fila(nit="12345", **{"890201": 1.0}),
             _fila(nit="901000003", **{"890201": 1.0})]
    resumen, gateway, writer, uc, _ = _correr(filas, gateway=gateway)
    assert resumen["verificar"] == 3 and gateway.creadas == []
    assert _detalle(writer, "555555555")["detalle"].startswith("Sin tercero con N. identificacion = 555555555 en Odoo")
    assert _detalle(writer, "12345")["detalle"].startswith("NIT invalido en la pre-factura: '12345'")
    assert [e["que_falta"] for e in uc.registry.sin_factura] == ["NIT POR CREAR"] * 3


def test_t12_t13_t14_bloqueos_y_ya_subidas_de_la_configuracion():
    settings = InjectionSettings(nits_bloqueados={"900448167": "otro tercero"},
                                 empresas_bloqueadas={"SGS COLOMIA": "Error en libro consolidado"},
                                 ya_subidas={"900111111": 726280})
    filas = [_fila(**{"890201": 1.0}), _fila(nit="900448167", **{"890201": 1.0}),
             _fila(nit="901000002", empresa="SGS COLOMIA PRUEBA", **{"890201": 1.0})]
    _, gateway, writer, _, _ = _correr(filas, settings=settings)
    assert gateway.creadas == []
    ya = _detalle(writer)
    assert (ya["estado"], ya["factura_id"]) == ("OK", 726280)
    assert ya["detalle"] == "Ya subida antes (no se duplico). Factura ID 726280"
    assert _detalle(writer, "900448167")["detalle"] == "NIT bloqueado: otro tercero | EMPRESA ALFA SAS"
    assert _detalle(writer, "901000002")["detalle"].startswith("NO SE PUEDE SUBIR - Error en libro consolidado")


def test_t19_t23_t25_apartados_por_ciudad_y_producto_cuadran():
    filas = [_fila(cedula="1", **{"890201": 1.0, "999999": 5000.0}),
             _fila(cedula="2", ciudad="PUEBLO INVENTADO", **{"890201": 1.0})]
    _, gateway, writer, uc, logger = _correr(filas, cols=("890201", "999999"))
    assert [l[2]["quantity"] for l in gateway.creadas[0]["vals"]["invoice_line_ids"]] == [1]
    problemas = sorted((p["codigo"], p["problema"]) for p in uc.registry.pendientes)
    assert problemas == [("890201", "SIN CUENTA ANALITICA"), ("999999", "PRODUCTO NO ENCONTRADO")]
    assert all(p["factura_id"] == 9001 for p in uc.registry.pendientes)
    assert not any("DESCUADRE" in e for e in logger.errors)
    assert "FALTAN 2 examenes" in _detalle(writer)["detalle"]


def test_t26_sin_lineas_va_a_verificar():
    _, gateway, writer, _, _ = _correr([_fila(ciudad="PUEBLO INVENTADO", **{"890201": 1.0})])
    assert gateway.creadas == []
    assert _detalle(writer)["detalle"].startswith("Ninguna linea se pudo armar. Ciudades sin cuenta: PUEBLO INVENTADO.")


def test_t11_cobro_doble_se_avisa_en_el_detalle():
    filas = [_fila(cedula="1", ingreso="9", **{"890201": 1.0}), _fila(cedula="1", ingreso="9", **{"890201": 1.0})]
    _, _, writer, _, _ = _correr(filas)
    assert "OJO cobro doble: el paciente 1 (ingreso 9) esta en 2 filas y repite 890201" in _detalle(writer)["detalle"]


def test_guarda_anti_duplicados_no_crea_si_ya_existe_hoy():
    gateway = FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI],
                                   drafts=[{"id": 8800, "partner_id": 505}])
    _, gateway, writer, _, _ = _correr([_fila(**{"890201": 1.0})], gateway=gateway)
    assert gateway.creadas == []
    assert _detalle(writer)["detalle"] == "Ya existia (no se duplico). Factura ID 8800"


def test_reintenta_la_empresa_ante_fallo_de_red_y_reconecta():
    esperas = []
    gateway = FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI], fallas_red=2)
    resumen, gateway, _, _, _ = _correr([_fila(**{"890201": 1.0})], gateway=gateway, sleep=esperas.append)
    assert resumen["ok"] == 1 and esperas == [10, 10] and gateway.conexiones == 3


def test_tres_fallos_de_red_dejan_error():
    gateway = FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI], fallas_red=3)
    resumen, _, writer, _, _ = _correr([_fila(**{"890201": 1.0})], gateway=gateway)
    assert resumen["errores"] == 1 and _detalle(writer)["detalle"] == "Red: red caída"


def test_t29_actualizar_precios_encendido():
    gateway = FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI], amount=125000.0)
    _, gateway, writer, _, _ = _correr([_fila(**{"890201": 1.0})], gateway=gateway, config={"actualizar_precios": True})
    r = _detalle(writer)
    assert (r["precios"], r["total"]) == ("ACTUALIZADOS", 125000.0) and gateway.precios_actualizados == [9001]


def test_t29_actualizar_precios_sin_tarifa():
    gateway = FakeInjectionGateway(partners=[TERCERO], products=PRODUCTOS, accounts=[CUENTA_CALI],
                                   price_error="Falta tarifa  para 890201\n CALI")
    _, _, writer, _, _ = _correr([_fila(**{"890201": 1.0})], gateway=gateway, config={"actualizar_precios": True})
    r = _detalle(writer)
    assert r["precios"] == "SIN TARIFA" and r["total"] == ""
    assert r["detalle"].endswith(" || PRECIOS EN 1: Falta tarifa para 890201 CALI")


def test_t1_archivo_ilegible_encabeza_el_log_y_se_copia_a_verificar():
    archivos = {"b.xlsx": ([_fila(**{"890201": 1.0})], ["890201"]),
                "a.xlsx": ValueError("La plantilla cambio: faltan las columnas NIT")}
    _, _, writer, _, _ = _correr(None, archivos=archivos)
    primero = writer.ultimos_resultados[0]
    assert (primero["empresa"], primero["estado"]) == ("a.xlsx", "ERROR")
    assert primero["detalle"] == "NO SE PUDO LEER EL ARCHIVO — La plantilla cambio: faltan las columnas NIT"
    assert writer.verificar == ["a.xlsx"]


def test_t9_filas_sin_nit_no_se_facturan():
    resumen, _, _, _, logger = _correr([_fila(nit=None, **{"890201": 1.0}), _fila(**{"890201": 1.0})])
    assert resumen["empresas"] == 1
    assert any("1 filas SIN NIT" in e for e in logger.errors)


def test_sin_archivos_no_conecta_ni_escribe_libros():
    resumen, gateway, writer, _, _ = _correr(None, archivos={})
    assert resumen is None and gateway.conexiones == 0 and writer.escrituras_de_libros == 0


def test_libros_se_guardan_cada_10_empresas_y_al_final():
    filas = [_fila(nit=str(900000000 + i), **{"890201": 1.0}) for i in range(10)]
    _, _, writer, _, _ = _correr(filas)
    assert writer.escrituras_de_libros == 2
