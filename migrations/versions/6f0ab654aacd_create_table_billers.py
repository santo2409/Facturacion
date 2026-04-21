"""create table billers

Revision ID: 6f0ab654aacd
Revises: bc1d152a1ddb
Create Date: 2026-02-21 13:58:14.826739

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6f0ab654aacd"
down_revision: Union[str, Sequence[str], None] = "bc1d152a1ddb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("billers")
