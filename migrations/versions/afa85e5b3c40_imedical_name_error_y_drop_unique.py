"""imedical_name_error_y_drop_unique

Revision ID: afa85e5b3c40
Revises: b3f8c1d92e07
Create Date: 2026-09-22 00:00:00.000000

Contexto (spec 008): la tabla `imedical` mapea `nit_error -> nit_success`, pero solo
guardaba el nombre correcto. Para el auto-registro (RF-09) se necesita conservar
también la razón social tal como venía en el Excel, de ahí `name_error`.

Además, `nit_success` tenía una restricción UNIQUE que impide que dos `nit_error`
distintos (p. ej. un NIT con dígito de verificación pegado y una cédula mal
digitada) apunten al mismo NIT correcto — escenario real y frecuente en los datos
de producción. La PK sobre `nit_error` sigue impidiendo duplicados reales.

ADVERTENCIA: el downgrade fallará si para entonces existen `nit_success`
duplicados en la tabla (esperable una vez el auto-registro lleve corriendo un
tiempo). Es una migración prácticamente irreversible en la práctica.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "afa85e5b3c40"
down_revision: Union[str, Sequence[str], None] = "b3f8c1d92e07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("imedical", sa.Column("name_error", sa.String(255), nullable=True))
    op.drop_constraint("imedical_nit_success_key", "imedical", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("imedical_nit_success_key", "imedical", ["nit_success"])
    op.drop_column("imedical", "name_error")
