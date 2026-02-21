"""create table type activities

Revision ID: 0d916af0d32e
Revises: 1f61750cbea8
Create Date: 2026-02-21 13:14:03.990088

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d916af0d32e"
down_revision: Union[str, Sequence[str], None] = "1f61750cbea8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
            CREATE TABLE `type_activities` (
                `id` int(11) NOT NULL AUTO_INCREMENT,
                `name` enum('INTRA','EXTRA') DEFAULT 'INTRA',
                `created_at` timestamp NULL DEFAULT current_timestamp(),
                `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                PRIMARY KEY (`id`),
                UNIQUE KEY `name` (`name`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)


def downgrade() -> None:
    op.drop_table("DROP TABLE type_activities;")
