from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e8b7d2a64"
down_revision: str | None = "9a4b7c2e1d05"
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
