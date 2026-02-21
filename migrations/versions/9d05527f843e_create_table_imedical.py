"""create table imedical

Revision ID: 9d05527f843e
Revises: 1b84dfcf8970
Create Date: 2026-02-21 13:46:31.532264

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d05527f843e"
down_revision: Union[str, Sequence[str], None] = "1b84dfcf8970"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `imedical` (
                    `nit_error` varchar(50) NOT NULL,
                    `name` varchar(255) NOT NULL,
                    `nit_success` varchar(12) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    UNIQUE KEY `nit_success` (`nit_success`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("imedical")
