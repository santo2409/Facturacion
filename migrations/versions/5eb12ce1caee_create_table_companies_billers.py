"""create table companies_billers

Revision ID: 5eb12ce1caee
Revises: bcd74cdfe32d
Create Date: 2026-02-21 14:31:18.523644

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5eb12ce1caee"
down_revision: Union[str, Sequence[str], None] = "bcd74cdfe32d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `companies_billers` (
                    `biller_id` int(11) NOT NULL,
                    `company_id` int(11) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    UNIQUE KEY `unique_company` (`company_id`),
                    CONSTRAINT `companies_billers_companies_FK` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("companies_billers")
