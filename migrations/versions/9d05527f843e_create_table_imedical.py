"""create table imedical

Revision ID: 9d05527f843e
Revises: 1b84dfcf8970
Create Date: 2026-02-21 13:46:31.532264

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9d05527f843e"
down_revision: Union[str, Sequence[str], None] = "1b84dfcf8970"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imedical",
        sa.Column("nit_error", sa.String(50), nullable=False, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("nit_success", sa.String(12), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("nit_success"),
    )


def downgrade() -> None:
    op.drop_table("imedical")
