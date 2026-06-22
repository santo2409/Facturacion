"""create table specials

Revision ID: 48ae35fa49f9
Revises: 7608e3498949
Create Date: 2026-02-21 14:11:34.296829

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "48ae35fa49f9"
down_revision: Union[str, Sequence[str], None] = "7608e3498949"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "specials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("specials")
