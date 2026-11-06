"""create table rates

Revision ID: bc1d152a1ddb
Revises: 5eb12ce1caee
Create Date: 2026-02-21 13:51:04.506406

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bc1d152a1ddb"
down_revision: Union[str, Sequence[str], None] = "5eb12ce1caee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rates",
        sa.Column("rateable_id", sa.Integer, nullable=False),
        sa.Column("city_id", sa.Integer, sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("cup_id", sa.Integer, sa.ForeignKey("cups.id"), nullable=False),
        sa.Column("rate", sa.BigInteger, nullable=False),
        sa.Column("activity_id", sa.Integer, sa.ForeignKey("type_activities.id"), nullable=False),
        sa.Column("rateable_type", sa.String(200), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP, nullable=True),
        sa.PrimaryKeyConstraint("rateable_id", "city_id", "cup_id", "activity_id", "rateable_type"),
    )


def downgrade() -> None:
    op.drop_table("rates")
