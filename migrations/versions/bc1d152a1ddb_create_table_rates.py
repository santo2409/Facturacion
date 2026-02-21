"""create table rates

Revision ID: bc1d152a1ddb
Revises: 9d05527f843e
Create Date: 2026-02-21 13:51:04.506406

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc1d152a1ddb"
down_revision: Union[str, Sequence[str], None] = "9d05527f843e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
                CREATE TABLE `rates` (
                    `rateable_id` int(11) NOT NULL,
                    `city_id` int(11) NOT NULL,
                    `cup_id` int(11) NOT NULL,
                    `rate` bigint(20) NOT NULL,
                    `activity_id` int(11) NOT NULL,
                    `rateable_type` varchar(200) NOT NULL,
                    `created_at` timestamp NULL DEFAULT current_timestamp(),
                    `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
                    PRIMARY KEY (`rateable_id`,`city_id`,`cup_id`,`activity_id`,`rateable_type`),
                    UNIQUE KEY `unique_rate` (`rateable_id`,`city_id`,`cup_id`,`activity_id`,`rateable_type`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)


def downgrade() -> None:
    op.drop_table("rates")
