"""remove_invalid_company_documents

Elimina 2 registros de `companies` cuyo documento no corresponde ni a un NIT
empresarial válido ni a una cédula: el décimo dígito no coincide con el DV
DIAN calculado sobre los primeros 9, y ninguno tiene vinculación en
companies_packages ni companies_billers (verificado antes de escribir esta
migración). Ver specs/006_normalizacion-nit-y-dedup-vinculaciones/spec.md,
RF-11.

Revision ID: b3f8c1d92e07
Revises: a1c2d3e4f5a6
Create Date: 2026-09-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b3f8c1d92e07"
down_revision: Union[str, Sequence[str], None] = "a1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REMOVED = [
    ("4444444444", "ACMI MEXICO"),
    ("8300291028", "FRANCY GISSEL LOPEZ CARO"),
]


def upgrade() -> None:
    # DELETE por nit: idempotente por naturaleza, si ya no existen borra 0 filas.
    op.execute(
        "DELETE FROM companies WHERE nit IN ('4444444444', '8300291028')"
    )


def downgrade() -> None:
    for nit, name in _REMOVED:
        op.execute(
            "INSERT INTO companies (nit, name, verified_at, created_at, updated_at) "
            f"VALUES ('{nit}', '{name}', now(), now(), now()) "
            "ON CONFLICT (nit) DO NOTHING"
        )
