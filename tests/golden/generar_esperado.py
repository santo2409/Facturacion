"""Ejecuta el sistema actual sobre tests/golden/entradas/ y guarda las salidas en
tests/golden/esperado/<escenario>.json.

    python tests/golden/generar_esperado.py                 # solo escenarios sin esperado
    python tests/golden/generar_esperado.py --forzar NOMBRE  # sobrescribe uno (requiere aprobación)

Regla del proyecto (CLAUDE.md, regla 3): nunca regenerar un esperado para que una
prueba pase. Solo se regenera cuando el cambio de comportamiento fue aprobado, y se
indica en el commit qué hallazgo lo justifica.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from tests.golden._arnes import ESCENARIOS, ESPERADO, ejecutar, serializar  # noqa: E402


def main(argv: list[str]) -> None:
    forzar = "--forzar" in argv
    nombres = [a for a in argv if not a.startswith("--")]
    if forzar and not nombres:
        sys.exit("--forzar exige nombrar los escenarios a sobrescribir.")
    desconocidos = set(nombres) - set(ESCENARIOS)
    if desconocidos:
        sys.exit(f"Escenarios desconocidos: {sorted(desconocidos)}")

    ESPERADO.mkdir(exist_ok=True)
    for nombre in nombres or ESCENARIOS:
        destino = ESPERADO / f"{nombre}.json"
        if destino.exists() and not forzar:
            print(f"= {nombre}: ya existe, se conserva")
            continue
        with pytest.MonkeyPatch.context() as mp, tempfile.TemporaryDirectory() as tmp:
            texto = serializar(ejecutar(nombre, Path(tmp) / "trabajo", mp))
        destino.write_text(texto, encoding="utf-8")
        print(f"+ {nombre}: {destino.relative_to(ESPERADO.parent.parent.parent)}")


if __name__ == "__main__":
    main(sys.argv[1:])
