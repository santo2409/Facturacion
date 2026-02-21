"""create table companies

Revision ID: 6dfd72ff3fa3
Revises: ed47e04eb066
Create Date: 2026-02-21 14:20:36.194505

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6dfd72ff3fa3"
down_revision: Union[str, Sequence[str], None] = "ed47e04eb066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(""" 
                CREATE TABLE `companies` (
                    `id` int(11) NOT NULL AUTO_INCREMENT,
                    `nit` varchar(12) NOT NULL,
                    `name` varchar(255) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `nit` (`nit`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("companies")
