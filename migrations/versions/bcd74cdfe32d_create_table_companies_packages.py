"""create table companies_packages

Revision ID: bcd74cdfe32d
Revises: 6dfd72ff3fa3
Create Date: 2026-02-21 14:25:29.321976

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bcd74cdfe32d"
down_revision: Union[str, Sequence[str], None] = "6dfd72ff3fa3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies_packages",
        sa.Column(
            "company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("package_id", sa.Integer, nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.PrimaryKeyConstraint("company_id", "package_id", "model"),
        sa.UniqueConstraint("company_id"),
    )


def downgrade() -> None:
    op.drop_table("companies_packages")
