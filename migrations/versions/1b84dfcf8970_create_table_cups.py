"""create table cups

Revision ID: 1b84dfcf8970
Revises: 0d916af0d32e
Create Date: 2026-02-21 13:43:00.685447

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b84dfcf8970"
down_revision: Union[str, Sequence[str], None] = "0d916af0d32e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `cups` (
                    `id` int(11) NOT NULL AUTO_INCREMENT,
                    `code` char(9) NOT NULL,
                    `name` varchar(255) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `code` (`code`),
                    UNIQUE KEY `name` (`name`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)


def downgrade() -> None:
    op.execute("""
                DROP TABLE `cups`;
            """)
