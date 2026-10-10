"""Guardián de la suite: un nombre de test repetido en el mismo módulo o clase
hace que Python conserve solo la última definición y la anterior nunca corra
(spec 013)."""
import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent


def find_duplicate_test_names(path: Path) -> list[str]:
    """['archivo:ámbito:nombre', ...] de funciones test_* repetidas en el módulo
    o dentro de una misma clase."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scopes = [("módulo", tree.body)] + [
        (node.name, node.body) for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]
    duplicates = []
    for scope, body in scopes:
        seen: set[str] = set()
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            if node.name in seen:
                duplicates.append(f"{path.name}:{scope}:{node.name}")
            seen.add(node.name)
    return duplicates


def test_finds_duplicate_at_module_level(tmp_path):
    f = tmp_path / "test_a.py"
    f.write_text("def test_x():\n    pass\n\ndef test_x():\n    pass\n")

    assert find_duplicate_test_names(f) == ["test_a.py:módulo:test_x"]


def test_finds_duplicate_inside_a_class(tmp_path):
    f = tmp_path / "test_b.py"
    f.write_text("class TestA:\n    def test_y(self):\n        pass\n\n    def test_y(self):\n        pass\n")

    assert find_duplicate_test_names(f) == ["test_b.py:TestA:test_y"]


def test_ignores_same_name_in_different_classes(tmp_path):
    f = tmp_path / "test_c.py"
    f.write_text(
        "class TestA:\n    def test_z(self):\n        pass\n\n"
        "class TestB:\n    def test_z(self):\n        pass\n"
    )

    assert find_duplicate_test_names(f) == []


def test_ignores_non_test_functions(tmp_path):
    f = tmp_path / "test_d.py"
    f.write_text("def helper():\n    pass\n\ndef helper():\n    pass\n")

    assert find_duplicate_test_names(f) == []


def test_no_duplicate_test_names_in_suite():
    offenders = [
        duplicate
        for path in sorted(TESTS_DIR.rglob("test_*.py"))
        for duplicate in find_duplicate_test_names(path)
    ]

    assert offenders == [], f"Tests con nombre duplicado (solo corre el último): {offenders}"
