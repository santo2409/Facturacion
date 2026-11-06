"""AUD-44: vigila la diferencia entre models.py y el esquema que crean las migraciones.

No conecta a ninguna BD: compara el DDL de `alembic upgrade head --sql` (modo
offline) con los metadatos del ORM. `models.py` todavía no está alineado (ver
docs/auditoria.md AUD-44), así que la diferencia conocida se lista aquí: la
prueba falla si aparece una diferencia NUEVA o si una conocida se corrige (en ese
caso, quítala de la lista). Mientras exista diferencia, no usar
`alembic revision --autogenerate`: propondría borrar columnas y tablas.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.shared.database.database import Base
import src.shared.database.models  # noqa: F401 - registra los modelos

ROOT = Path(__file__).resolve().parents[2]

KNOWN_MISSING_COLUMNS = {
    (t, "deleted_at") for t in (
        "billers", "cities", "companies", "companies_billers", "companies_packages", "cups",
        "packages", "providers", "rates", "specials", "type_activities",
    )
}
KNOWN_TABLES_WITHOUT_MODEL = {"roles", "permissions", "role_permissions", "users"}
KNOWN_MISSING_FKS = {
    ("companies_billers", "biller_id", "billers"),
    ("rates", "activity_id", "type_activities"),
    ("rates", "city_id", "cities"),
    ("rates", "cup_id", "cups"),
    ("role_permissions", "permission_id", "permissions"),
    ("role_permissions", "role_id", "roles"),
    ("users", "role_id", "roles"),
}


@pytest.fixture(scope="module")
def migration_schema():
    ddl = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    columns: dict[str, set[str]] = {}
    fks: set[tuple[str, str, str]] = set()
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", ddl, re.S):
        lines = [line.strip() for line in body.split("\n") if line.strip()]
        columns[name] = {
            line.split()[0] for line in lines
            if not line.startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CHECK"))
        }
        fks |= {(name, col, ref) for col, ref in re.findall(r"FOREIGN KEY\((\w+)\) REFERENCES (\w+)", body)}
    for table, col in re.findall(r"ALTER TABLE (\w+) ADD COLUMN (\w+)", ddl):
        columns.setdefault(table, set()).add(col)
    for table, col in re.findall(r"ALTER TABLE (\w+) DROP COLUMN (\w+)", ddl):
        columns.get(table, set()).discard(col)
    for table in re.findall(r"DROP TABLE (\w+)", ddl):
        columns.pop(table, None)
    columns.pop("alembic_version", None)
    return columns, fks


def test_models_match_migrations_except_known_gaps(migration_schema):
    mig_columns, mig_fks = migration_schema
    model_columns = {t.name: set(t.columns.keys()) for t in Base.metadata.sorted_tables}
    model_fks = {
        (t.name, fk.parent.name, fk.column.table.name)
        for t in Base.metadata.sorted_tables for fk in t.foreign_keys
    }

    tables_without_model = set(mig_columns) - set(model_columns)
    models_without_table = set(model_columns) - set(mig_columns)
    missing_columns = {
        (t, c) for t in set(mig_columns) & set(model_columns) for c in mig_columns[t] - model_columns[t]
    }
    extra_columns = {
        (t, c) for t in set(mig_columns) & set(model_columns) for c in model_columns[t] - mig_columns[t]
    }

    assert models_without_table == set()
    assert extra_columns == set()
    assert tables_without_model == KNOWN_TABLES_WITHOUT_MODEL
    assert missing_columns == KNOWN_MISSING_COLUMNS
    assert mig_fks - model_fks == KNOWN_MISSING_FKS
    assert model_fks - mig_fks == set()
