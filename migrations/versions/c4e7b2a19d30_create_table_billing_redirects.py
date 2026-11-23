"""create table billing_redirects

Revision ID: c4e7b2a19d30
Revises: afa85e5b3c40
Create Date: 2026-11-23 00:00:00.000000

Redirecciones de facturación genéricas (generaliza `tian`): cada fila dice que
las atenciones de `nit_origen` se facturan bajo `nit_destino` con el sufijo
"(<etiqueta>)" en la Empresa. La tabla `tian` y TIAN_NIT siguen funcionando igual.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7b2a19d30"
down_revision: Union[str, Sequence[str], None] = "afa85e5b3c40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_redirects",
        sa.Column("nit_origen", sa.String(50), nullable=False, primary_key=True),
        sa.Column("nit_destino", sa.String(50), nullable=False),
        sa.Column("etiqueta", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("billing_redirects")
