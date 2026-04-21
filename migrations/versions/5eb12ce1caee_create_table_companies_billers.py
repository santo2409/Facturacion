"""create table companies_billers

Revision ID: 5eb12ce1caee
Revises: bcd74cdfe32d
Create Date: 2026-02-21 14:31:18.523644

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5eb12ce1caee"
down_revision: Union[str, Sequence[str], None] = "bcd74cdfe32d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies_billers",
        sa.Column("biller_id", sa.Integer, nullable=False, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id"),
    )


def downgrade() -> None:
    op.drop_table("companies_billers")
