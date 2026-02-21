"""create table companies_packages

Revision ID: bcd74cdfe32d
Revises: 6dfd72ff3fa3
Create Date: 2026-02-21 14:25:29.321976

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bcd74cdfe32d"
down_revision: Union[str, Sequence[str], None] = "6dfd72ff3fa3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `companies_packages` (
                    `company_id` int(11) NOT NULL,
                    `package_id` int(11) NOT NULL,
                    `model` varchar(60) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    PRIMARY KEY (`company_id`,`package_id`,`model`),
                    UNIQUE KEY `company_id` (`company_id`),
                    CONSTRAINT `companies_packages_ibfk_1` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("companies_packages")
