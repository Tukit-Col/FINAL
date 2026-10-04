"""tabla kit_canonico

Revision: 5c1e8b7d2a64
Anterior: 3d8f5a1c9e42
Fecha:    2026-09-28 19:00:00.000000+00:00

Por que este cambio: el modelo `KitCanonico` (el puntero a los kits benditos de
un colegio, grado y anio) se agrego sin su revision. `create_all` lo creaba,
pero una base levantada con `make backend` pasa por las migraciones y se
quedaba sin la tabla: `/v1/grados-canonicos` respondia 500 y la pantalla de
Empezar del acudiente no cargaba. `make bd-deriva` lo marcaba como `add_table`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e8b7d2a64"
down_revision: str | None = "3d8f5a1c9e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kit_canonico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.String(length=64), nullable=False),
        sa.Column("grado", sa.String(length=64), nullable=False),
        sa.Column("anio_lectivo", sa.Integer(), nullable=False),
        sa.Column("trabajo_id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["trabajo_id"], ["trabajo_pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("colegio_id", "grado", "anio_lectivo", name="uq_kit_canonico_grado"),
    )


def downgrade() -> None:
    op.drop_table("kit_canonico")
