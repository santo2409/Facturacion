"""T19: resolución de la cuenta analítica por sede y ciudad, sin respaldo a Bogotá."""
from src.odooInjection.domain.services.analytic_account_resolver import AnalyticAccountResolver
from tests.fakes.fake_injection_gateway import FakeInjectionGateway
from tests.fakes.fake_logger import FakeLogger

CUENTAS = [
    {"id": 1, "code": "AA8638", "name": "SALUD OCUPACIONAL DE LOS ANDES LTDA - INTRAMURAL - SEDE 103 - BOGOTA D.C."},
    {"id": 2, "code": "AA8637", "name": "SALUD OCUPACIONAL DE LOS ANDES LTDA - INTRAMURAL - ZONA INDUSTRIAL - BOGOTA D.C."},
    {"id": 3, "code": "AA10344", "name": "SALUD OCUPACIONAL DE LOS ANDES LTDA - EXTRAMURAL - EXTRAMURAL - BOGOTA D.C."},
    {"id": 4, "code": "AA10405", "name": "SEDE SOA - PROVEEDORES - CALI"},
    {"id": 5, "code": None, "name": "SEDE SOA - PROVEEDORES - MARIQUITA"},
    {"id": 6, "code": "AA99999", "name": "SEDE SOA - PROVEEDORES - TABIO"},
    {"id": 11136, "code": None, "name": "SEDE SOA - PROVEEDORES - MARIQUITA"},
]


def _resolver(cuentas=CUENTAS):
    return AnalyticAccountResolver(FakeInjectionGateway(accounts=cuentas), FakeLogger())


def test_t19_la_sede_manda_sobre_la_ciudad():
    assert _resolver().resolver("BOGOTA D.C.", "ZONA INDUSTRIAL")[0] == 2
    assert _resolver().resolver("BOGOTA D.C.", "SEDE 103")[0] == 1


def test_t19_sede_103_en_otra_ciudad_queda_apartada():
    cid, _, motivo = _resolver().resolver("CALI", "SEDE 103")
    assert cid is None and "revisar SEDE_CUENTA" in motivo


def test_t19_extramural_va_a_la_extramural_de_su_ciudad():
    assert _resolver().resolver("BOGOTA, D.C.", "EXTRAMURAL SERVICIO A DOMICILIO")[0] == 3


def test_t19_ciudad_por_id_y_por_codigo_confirmado_por_nombre():
    assert _resolver().resolver("MARIQUITA", "SEDE X")[0] == 11136
    assert _resolver().resolver("CALI", None)[0] == 4


def test_t19_ciudad_fuera_del_mapa_busca_proveedores_por_nombre():
    logger = FakeLogger()
    cid, etiqueta, _ = AnalyticAccountResolver(FakeInjectionGateway(accounts=CUENTAS), logger).resolver("TABIO", None)
    assert cid == 6 and "TABIO" in etiqueta
    assert any("no esta en el mapa" in w for w in logger.warnings)


def test_t19_sin_respaldo_a_bogota():
    cid, _, motivo = _resolver().resolver("PUEBLO INVENTADO", None)
    assert cid is None and "no esta en el mapa" in motivo


def test_t19_codigo_repetido_desempata_por_nombre():
    cuentas = CUENTAS + [{"id": 7, "code": "AA10405", "name": "SEDE SOA - PROVEEDORES - SAN JUAN"}]
    assert _resolver(cuentas).resolver("CALI", None)[0] == 4


def test_t19_indice_se_consulta_una_vez():
    gateway = FakeInjectionGateway(accounts=CUENTAS)
    llamadas = []
    original = gateway.analytic_accounts_all
    gateway.analytic_accounts_all = lambda: llamadas.append(1) or original()
    resolver = AnalyticAccountResolver(gateway, FakeLogger())
    resolver.resolver("CALI", None)
    resolver.resolver("TABIO", None)
    assert llamadas == [1]
