"""create table type activities

Revision ID: 0d916af0d32e
Revises: 1f61750cbea8
Create Date: 2026-02-21 13:14:03.990088

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0d916af0d32e"
down_revision: Union[str, Sequence[str], None] = "1f61750cbea8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "type_activities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(10), nullable=False, server_default="INTRA"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("name IN ('INTRA', 'EXTRA')"),
    )


def downgrade() -> None:
    op.drop_table("type_activities")
