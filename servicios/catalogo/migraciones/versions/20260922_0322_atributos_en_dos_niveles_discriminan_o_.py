from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401
from sqlalchemy.dialects import postgresql

revision: str = "4b1c8a2f6d33"
down_revision: str | None = "79d641af049e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LISTA = sa.JSON().with_variant(postgresql.ARRAY(sa.String()), "postgresql")


def upgrade() -> None:
    op.alter_column("concepto", "atributos_requeridos", new_column_name="atributos_discriminantes")
    op.add_column(
        "concepto",
        sa.Column("atributos_descriptivos", _LISTA, nullable=False, server_default="{}"),
    )
    op.alter_column("concepto", "atributos_descriptivos", server_default=None)

    op.create_check_constraint(
        "concepto_atributos_sin_solapar",
        "concepto",
        "NOT (atributos_discriminantes && atributos_descriptivos)",
    )


def downgrade() -> None:
    op.drop_constraint("concepto_atributos_sin_solapar", "concepto", type_="check")
    op.execute(
        "UPDATE concepto SET atributos_discriminantes = atributos_discriminantes || atributos_descriptivos"
    )
    op.drop_column("concepto", "atributos_descriptivos")
    op.alter_column("concepto", "atributos_discriminantes", new_column_name="atributos_requeridos")
