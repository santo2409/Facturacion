"""create table tian

Revision ID: ed47e04eb066
Revises: 48ae35fa49f9
Create Date: 2026-02-21 14:14:35.452695

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ed47e04eb066"
down_revision: Union[str, Sequence[str], None] = "48ae35fa49f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tian",
        sa.Column("nit_error", sa.String(50), nullable=False, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tian")
