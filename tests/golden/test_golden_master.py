"""Golden master de Facturacion: regenera las salidas del sistema actual sobre
entradas fijas y las compara con las guardadas en tests/golden/esperado/.

Si falla, el sistema cambió de comportamiento. No se regenera el esperado para que
pase (CLAUDE.md, regla 3): se corrige el código o se consulta. Ver README.md.
"""

import difflib

import pytest

from tests.golden._arnes import ESCENARIOS, ESPERADO, ejecutar, serializar


@pytest.mark.parametrize("escenario", list(ESCENARIOS))
def test_golden_salidas_coinciden_con_esperado(escenario, tmp_path, monkeypatch):
    esperado_path = ESPERADO / f"{escenario}.json"
    assert esperado_path.exists(), (
        f"Falta {esperado_path.name}. Genéralo con: python tests/golden/generar_esperado.py"
    )
    obtenido = serializar(ejecutar(escenario, tmp_path / "trabajo", monkeypatch))
    esperado = esperado_path.read_text(encoding="utf-8")

    if obtenido != esperado:
        diff = "".join(difflib.unified_diff(
            esperado.splitlines(keepends=True), obtenido.splitlines(keepends=True),
            fromfile=f"esperado/{escenario}.json", tofile="obtenido", n=2,
        ))
        pytest.fail(f"El comportamiento de '{escenario}' cambió:\n{diff[:20000]}", pytrace=False)


def test_golden_cada_escenario_tiene_entradas():
    from tests.golden._arnes import ENTRADAS

    faltantes = [n for n in ESCENARIOS if not (ENTRADAS / n).is_dir()]
    assert faltantes == []
