"""Opción 6: carga de empresas facturadas a otro NIT (billing_redirects) desde Excel."""
import polars as pl

from src.company.application.use_cases.import_billing_redirects_from_excel import (
    ImportBillingRedirectsFromExcel,
)
from tests.fakes.fake_biller_company_repo import FakeBillerCompanyRepo
from tests.fakes.fake_billing_redirect_repo import FakeBillingRedirectRepo
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_findings_writer import FakeFindingsWriter
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_tian_repo import FakeTianRepo


def _deps(redirects=None, tian=None, falla=False):
    companies = FakeCompanyRepo([
        {"id": 1, "nit": "860507033", "name": "VISE LTDA"},
        {"id": 2, "nit": "900494134", "name": "RSG SAS"},
        {"id": 3, "nit": "830068110", "name": "ASTAF SAS"},
        {"id": 4, "nit": "900293402", "name": "TIAN IPS SAS"},
    ])
    companies._packages = [{"company": c, "package": 9, "model": "Special"} for c in (1, 3, 4)]
    billers = FakeBillerCompanyRepo()
    billers._data = [{"company": 1, "biller": 1}, {"company": 4, "biller": 2}]
    return {
        "redirect_repo": FakeBillingRedirectRepo(redirects, falla=falla),
        "company_repo": companies,
        "biller_company_repo": billers,
        "tian_repo": FakeTianRepo(tian or []),
        "findings_writer": FakeFindingsWriter(),
        "logger": FakeLogger(),
        "tian_nit": "900293402",
    }


def _df(filas, columnas=("NIT_ORIGEN", "NIT_DESTINO", "ETIQUETA", "NOMBRE")):
    return pl.DataFrame([dict(zip(columnas, f)) for f in filas], schema={c: pl.Utf8 for c in columnas})


def test_redirecciones_carga_filas_validas_incluido_tian():
    deps = _deps()
    df = _df([("101907357", "860507033", "vise", "DEAS LTDA ROLLS"),
              ("800.064.847", "900293402", "TIAN", "PROCESOS DE MANUFACTURA"),
              ("830121897", "830068110", "ASTAF", None)])
    resumen = ImportBillingRedirectsFromExcel(**deps).execute(df)
    assert resumen == {"nuevas": 3, "actualizadas": 0, "desactivadas": 0, "errores": 0}
    assert {r["nit_origen"]: (r["nit_destino"], r["etiqueta"]) for r in deps["redirect_repo"].all()} == {
        "101907357": ("860507033", "VISE"), "800064847": ("900293402", "TIAN"), "830121897": ("830068110", "ASTAF")}


def test_redirecciones_actualiza_existentes_y_no_toca_las_que_no_vienen():
    deps = _deps(redirects=[{"nit_origen": "101907357", "nit_destino": "830068110", "etiqueta": "ASTAF", "name": None},
                            {"nit_origen": "999999999", "nit_destino": "860507033", "etiqueta": "VISE", "name": None}])
    resumen = ImportBillingRedirectsFromExcel(**deps).execute(_df([("101907357", "860507033", "VISE", None)]))
    assert (resumen["nuevas"], resumen["actualizadas"]) == (0, 1)
    assert {r["nit_origen"] for r in deps["redirect_repo"].all()} == {"101907357", "999999999"}


def test_redirecciones_columnas_con_espacios_y_minusculas():
    deps = _deps()
    df = _df([("101907357", "860507033", "VISE", None)], columnas=(" nit origen", "Nit Destino ", "etiqueta", "nombre"))
    assert ImportBillingRedirectsFromExcel(**deps).execute(df)["nuevas"] == 1


def test_redirecciones_sin_columnas_requeridas_no_carga_nada():
    deps = _deps()
    df = _df([("1", "2")], columnas=("NIT_ORIGEN", "ETIQUETA"))
    assert ImportBillingRedirectsFromExcel(**deps).execute(df) is None
    assert deps["redirect_repo"].all() == []
    assert any("NIT_DESTINO" in e for e in deps["logger"].errors)


def test_redirecciones_filas_con_error_no_se_cargan():
    deps = _deps()
    df = _df([("", "860507033", "VISE", None),
              ("101907357", "NIT 86", "VISE", None),
              ("101907357", "860507033", "", None),
              ("101907357", "860507033", "X" * 51, None),
              ("860507033", "860507033", "VISE", None),
              ("900293402", "860507033", "VISE", None),
              ("123456789.0", "860507033", "VISE", None)])
    resumen = ImportBillingRedirectsFromExcel(**deps).execute(df)
    motivos = [f["Motivo"] for f in deps["findings_writer"].books["filas_con_error"]]
    assert resumen["errores"] == 6 and resumen["nuevas"] == 1
    assert motivos[0] == "NIT origen vacío"
    assert "caracteres que no son dígitos" in motivos[1]
    assert motivos[2] == "Falta la etiqueta"
    assert "máximo es 50" in motivos[3]
    assert motivos[4] == "El NIT origen y el destino son el mismo"
    assert "TIAN_NIT" in motivos[5]
    assert [f["Fila"] for f in deps["findings_writer"].books["filas_con_error"]] == [2, 3, 4, 5, 6, 7]


def test_redirecciones_repetidas_gana_la_ultima():
    deps = _deps()
    df = _df([("101907357", "830068110", "ASTAF", None), ("101907357", "860507033", "VISE", None)])
    ImportBillingRedirectsFromExcel(**deps).execute(df)
    assert deps["redirect_repo"].all()[0]["etiqueta"] == "VISE"
    assert deps["findings_writer"].books["filas_repetidas"] == [{"Fila": 2, "NIT origen": "101907357", "Fila que queda": 3}]


def test_redirecciones_avisa_destinos_que_no_van_a_funcionar():
    deps = _deps()
    df = _df([("900123408", "900494134", "RSG", None), ("900154981", "900494134", "RSG", None),
              ("830121897", "830068110", "ASTAF", None), ("901000001", "901999999", "NUEVA", None)])
    ImportBillingRedirectsFromExcel(**deps).execute(df)
    revisar = {f["NIT destino"]: (f["Empresas"], f["Motivo"]) for f in deps["findings_writer"].books["destinos_por_revisar"]}
    assert revisar["900494134"][0] == 2 and "No tiene paquete" in revisar["900494134"][1]
    assert "No tiene facturador" in revisar["830068110"][1]
    assert "No existe en la BD" in revisar["901999999"][1]
    assert "860507033" not in revisar
    assert len(deps["redirect_repo"].all()) == 4          # se cargan igual


def test_redirecciones_avisa_origen_que_ya_esta_en_tian():
    deps = _deps(tian=[{"nit_error": "800064847", "name": "X"}])
    ImportBillingRedirectsFromExcel(**deps).execute(_df([("800064847", "900293402", "TIAN", None)]))
    assert deps["findings_writer"].books["origenes_en_tian"][0]["NIT origen"] == "800064847"


def test_redirecciones_activo_no_desactiva():
    deps = _deps(redirects=[{"nit_origen": "101907357", "nit_destino": "860507033", "etiqueta": "VISE", "name": None}])
    df = _df([("101907357", "", "", None, "no"), ("555555555", "", "", None, "NO")],
             columnas=("NIT_ORIGEN", "NIT_DESTINO", "ETIQUETA", "NOMBRE", "ACTIVO"))
    resumen = ImportBillingRedirectsFromExcel(**deps).execute(df)
    assert resumen["desactivadas"] == 1 and deps["redirect_repo"].all() == []
    assert [d["Resultado"] for d in deps["findings_writer"].books["desactivadas"]] == [
        "Desactivada", "No estaba activa: sin cambios"]


def test_redirecciones_si_falla_la_bd_no_reporta_exito():
    deps = _deps(falla=True)
    assert ImportBillingRedirectsFromExcel(**deps).execute(_df([("101907357", "860507033", "VISE", None)])) is None


def test_redirecciones_filas_vacias_se_ignoran_y_sin_hallazgos_no_hay_libros():
    deps = _deps()
    resumen = ImportBillingRedirectsFromExcel(**deps).execute(
        _df([(None, None, None, None), ("101907357", "860507033", "VISE", None)]))
    assert resumen["nuevas"] == 1 and resumen["errores"] == 0
    assert deps["findings_writer"].books is None
