"""create table tian

Revision ID: ed47e04eb066
Revises: 48ae35fa49f9
Create Date: 2026-02-21 14:14:35.452695

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed47e04eb066"
down_revision: Union[str, Sequence[str], None] = "48ae35fa49f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `tian` (
                    `nit_error` varchar(50) NOT NULL,
                    `name` varchar(255) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    UNIQUE KEY `nit_error` (`nit_error`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("tian")
