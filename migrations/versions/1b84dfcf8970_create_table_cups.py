"""create table cups

Revision ID: 1b84dfcf8970
Revises: 0d916af0d32e
Create Date: 2026-02-21 13:43:00.685447

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1b84dfcf8970"
down_revision: Union[str, Sequence[str], None] = "0d916af0d32e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cups",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(9), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("cups")
