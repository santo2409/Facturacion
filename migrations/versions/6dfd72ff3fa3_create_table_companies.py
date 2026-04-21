"""create table companies

Revision ID: 6dfd72ff3fa3
Revises: ed47e04eb066
Create Date: 2026-02-21 14:20:36.194505

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6dfd72ff3fa3"
down_revision: Union[str, Sequence[str], None] = "ed47e04eb066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("nit", sa.String(12), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("nit"),
    )


def downgrade() -> None:
    op.drop_table("companies")
