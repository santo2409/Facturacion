"""create table packages

Revision ID: b0e0c5ccc922
Revises: 5b72cbe5e0ee
Create Date: 2026-02-21 14:04:04.994736

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0e0c5ccc922"
down_revision: Union[str, Sequence[str], None] = "5b72cbe5e0ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("packages")
