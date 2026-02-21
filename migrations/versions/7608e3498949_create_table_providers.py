"""create table providers

Revision ID: 7608e3498949
Revises: b0e0c5ccc922
Create Date: 2026-02-21 14:07:55.986103

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7608e3498949"
down_revision: Union[str, Sequence[str], None] = "b0e0c5ccc922"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
               CREATE TABLE `providers` (
                    `id` int(11) NOT NULL AUTO_INCREMENT,
                    `name` varchar(255) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `name` (`name`)
                    ) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("providers")
