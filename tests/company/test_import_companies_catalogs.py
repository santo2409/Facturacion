"""Tests para el catálogo unificado de paquetes robusto ante orígenes
vacíos (spec 007, hallazgo nº1 del verify.md del spec 006: RF-01 a RF-04).

`pl.DataFrame([])` produce un frame (0,0) sin columnas; al aplicarle
`.with_columns(pl.lit(...).alias("model"))` el resultado no es un frame
vacío sino uno de (1,1) con una fila fantasma. Estos tests fijan el
comportamiento correcto: ningún origen vacío debe aportar filas, y los
tres vacíos a la vez es una anomalía del flujo secuencial (opción 3 →
opción 4 → opción 5), no un caso a tolerar en silencio."""

import polars as pl
import pytest

from src.company.application.use_cases.import_companies_from_excel import ImportCompaniesFromExcel
from tests.fakes.fake_company_repo import FakeCompanyRepo
from tests.fakes.fake_fuzz import FakeFuzz
from tests.fakes.fake_logger import FakeLogger


class CapturingLogger(FakeLogger):
    """FakeLogger descarta `user_msg` (`def warning(self, msg, **_)`), así que
    los AC redactados sobre "el mensaje al usuario" no serían verificables con
    él. Este doble local captura ambos canales del logging dual."""

    def __init__(self):
        super().__init__()
        self.user_msgs = []

    def warning(self, msg, **kwargs):
        super().warning(msg, **kwargs)
        if kwargs.get("user_msg"):
            self.user_msgs.append(kwargs["user_msg"])

    def info(self, msg, **kwargs):
        super().info(msg, **kwargs)
        if kwargs.get("user_msg"):
            self.user_msgs.append(kwargs["user_msg"])
from tests.fakes.fake_nit_service import FakeNitService
from tests.fakes.fake_not_found_log_generator import FakeNotFoundLogGenerator
from tests.fakes.fake_not_linked_log_generator import FakeNotLinkedLogGenerator
from tests.fakes.fake_package_repo import FakePackageRepo
from tests.fakes.fake_progress import FakeProgress
from tests.fakes.fake_provider_repo import FakeProviderRepo
from tests.fakes.fake_special_repo import FakeSpecialRepo


@pytest.fixture
def deps(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORY", str(tmp_path))
    return {
        "company_repo": FakeCompanyRepo(initial=[{"id": 1, "nit": "900111111", "name": "EMPRESA A"}]),
        "package_repo": FakePackageRepo([{"id": 10, "name": "PAQUETE BASICO"}]),
        "provider_repo": FakeProviderRepo([]),
        "special_repo": FakeSpecialRepo([]),
        "fuzz": FakeFuzz(),
        "nit_service": FakeNitService(results=[]),
        "progress": FakeProgress(),
        "logger": CapturingLogger(),
        "not_found_log_generator": FakeNotFoundLogGenerator(),
        "logs_dir": tmp_path / "logs",
        "not_linked_log_generator": FakeNotLinkedLogGenerator(),
    }


def _df(rows):
    return pl.DataFrame(rows)


def test_catalogo_con_proveedores_vacio_no_lanza_shapeerror(deps):
    """AC-01: proveedores vacío, paquetes con datos → la vinculación se
    completa sin ShapeError y persiste con el catálogo de paquetes."""
    deps["special_repo"] = FakeSpecialRepo([{"id": 20, "name": "ESPECIAL X"}])
    uc = ImportCompaniesFromExcel(**deps)
    df = _df({
        "NIT": ["900111111"],
        "RAZON SOCIAL": ["EMPRESA A"],
        "PAQUETE": ["PAQUETE BASICO"],
    })

    uc._progress_companies_to_packages(df)  # no debe lanzar ShapeError

    assert uc._links_persisted == 1
    assert deps["company_repo"].batches[0][0].package_id == 10


def test_catalogo_con_especiales_vacio_no_lanza_shapeerror(deps):
    """AC-02: tarifas especiales vacío, paquetes con datos → sin error."""
    deps["provider_repo"] = FakeProviderRepo([{"id": 20, "name": "PROVEEDOR X"}])
    uc = ImportCompaniesFromExcel(**deps)
    df = _df({
        "NIT": ["900111111"],
        "RAZON SOCIAL": ["EMPRESA A"],
        "PAQUETE": ["PAQUETE BASICO"],
    })

    uc._progress_companies_to_packages(df)  # no debe lanzar ShapeError

    assert uc._links_persisted == 1


def test_catalogo_vacio_no_introduce_fila_fantasma(deps):
    """AC-03: un origen vacío no aporta ninguna fila al catálogo unificado;
    ninguna fila del catálogo tiene el nombre nulo o vacío."""
    deps["special_repo"] = FakeSpecialRepo([{"id": 20, "name": "ESPECIAL X"}])
    uc = ImportCompaniesFromExcel(**deps)

    todo = uc._build_package_catalog()

    assert todo.height == 2  # 1 paquete + 1 especial; providers vacío no aporta
    assert todo.columns == ["id", "name", "model"]
    assert all(n not in (None, "") for n in todo["name"].to_list())


def test_catalogo_vacio_advierte_senalando_paso_previo(deps):
    """AC-04: un catálogo vacío se advierte identificando el catálogo y
    señalando el paso previo del flujo (opción 3 y opción 4)."""
    deps["special_repo"] = FakeSpecialRepo([{"id": 20, "name": "ESPECIAL X"}])
    uc = ImportCompaniesFromExcel(**deps)

    uc._build_package_catalog()

    warnings = deps["logger"].warnings
    assert any("proveedores" in w.lower() for w in warnings)

    # segunda cláusula del AC: "el mensaje AL USUARIO indica que debe
    # ejecutarse antes el tratamiento de información y la carga de tarifas"
    user_msgs = deps["logger"].user_msgs
    assert any("proveedores" in m.lower() for m in user_msgs)
    assert any(
        "Tratamiento Información" in m and "Cargar Tarifas" in m for m in user_msgs
    )


def test_los_tres_catalogos_vacios_no_vincula_e_informa(deps):
    """AC-05: los tres catálogos vacíos → no se persiste ninguna
    vinculación, no se propaga excepción, se informa al usuario y todas
    las filas quedan reportadas en empresas_no_vinculadas.xlsx."""
    deps["package_repo"] = FakePackageRepo([])  # los tres orígenes vacíos
    uc = ImportCompaniesFromExcel(**deps)
    df = _df({
        "NIT": ["900111111", "900222222", "900333333"],
        "RAZON SOCIAL": ["EMPRESA A", "EMPRESA B", "EMPRESA C"],
        "PAQUETE": ["X", "Y", "Z"],
    })

    uc._progress_companies_to_packages(df)  # no debe lanzar excepción

    assert uc._links_persisted == 0
    assert uc._unlinked_count == 3
    assert deps["company_repo"].batches == []

    generator = deps["not_linked_log_generator"]
    assert len(generator.calls) == 1
    rows, _ = generator.calls[0]
    assert len(rows) == 3
    assert all("No hay catálogo de paquetes" in r.reason for r in rows)

    assert any(
        "no hay catálogo de paquetes" in msg.lower()
        for msg in deps["logger"].warnings + deps["logger"].infos
    )
    assert any(
        "no hay catálogo de paquetes" in m.lower() for m in deps["logger"].user_msgs
    ), "el AC exige informar AL USUARIO, no sólo en el log técnico"

    # última cláusula del AC: "el resumen agregado informa tres filas sin vincular"
    uc._emit_summary()
    assert any("3 fila(s) sin vincular" in msg for msg in deps["logger"].infos)
    assert any("Filas sin vincular: 3" in m for m in deps["logger"].user_msgs)
