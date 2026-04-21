"""create table providers

Revision ID: 7608e3498949
Revises: b0e0c5ccc922
Create Date: 2026-02-21 14:07:55.986103

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7608e3498949"
down_revision: Union[str, Sequence[str], None] = "b0e0c5ccc922"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("providers")
