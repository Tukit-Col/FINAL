from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401
from sqlalchemy.dialects import postgresql

revision: str = "7c679f269235"
down_revision: str | None = "82939e21610c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "propuesta_producto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concepto_id", sa.Uuid(), nullable=True),
        sa.Column("concepto_sugerido", sa.String(length=128), nullable=True),
        sa.Column("texto_origen", sa.Text(), nullable=False),
        sa.Column("tienda_id", sa.Uuid(), nullable=False),
        sa.Column("referencia_externa", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("nombre", sa.String(length=512), nullable=False),
        sa.Column("marca", sa.String(length=128), nullable=True),
        sa.Column("ean", sa.String(length=14), nullable=True),
        sa.Column("imagen_url", sa.Text(), nullable=True),
        sa.Column("precio_centavos", sa.BigInteger(), nullable=False),
        sa.Column("disponible", sa.Boolean(), nullable=False),
        sa.Column("especificaciones", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("nivel_sugerido", sa.String(length=16), nullable=True),
        sa.Column("puntaje", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=True),
        sa.Column(
            "propuesta_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resuelta_por", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "estado <> 'aprobada' OR producto_canonico_id IS NOT NULL",
            name="propuesta_aprobada_tiene_producto",
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aprobada', 'rechazada')", name="propuesta_estado_valido"
        ),
        sa.CheckConstraint(
            "nivel_sugerido IS NULL OR nivel_sugerido IN ('economico', 'confiable', 'premium')",
            name="propuesta_nivel_valido",
        ),
        sa.CheckConstraint(
            "concepto_id IS NOT NULL OR concepto_sugerido IS NOT NULL", name="propuesta_tiene_destino"
        ),
        sa.CheckConstraint("precio_centavos > 0", name="propuesta_precio_positivo"),
        sa.ForeignKeyConstraint(["concepto_id"], ["concepto.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_canonico_id"], ["producto_canonico.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tienda_id"], ["tienda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tienda_id", "referencia_externa", name="uq_propuesta_referencia"),
    )
    op.create_index("ix_propuesta_pendiente", "propuesta_producto", ["estado", "propuesta_en"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_propuesta_pendiente", table_name="propuesta_producto")
    op.drop_table("propuesta_producto")
