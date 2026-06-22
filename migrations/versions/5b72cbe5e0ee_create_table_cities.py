"""create table cities

Revision ID: 5b72cbe5e0ee
Revises: 6f0ab654aacd
Create Date: 2026-02-21 14:00:34.201533

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5b72cbe5e0ee"
down_revision: Union[str, Sequence[str], None] = "6f0ab654aacd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("cities")
