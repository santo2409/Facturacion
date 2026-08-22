"""add_verified_at_to_companies

Revision ID: a1c2d3e4f5a6
Revises: f60655fefc7f
Create Date: 2026-08-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "f60655fefc7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("verified_at", sa.TIMESTAMP(), nullable=True))
    op.execute(
        "UPDATE companies SET verified_at = COALESCE(updated_at, created_at, now())"
    )


def downgrade() -> None:
    op.drop_column("companies", "verified_at")
