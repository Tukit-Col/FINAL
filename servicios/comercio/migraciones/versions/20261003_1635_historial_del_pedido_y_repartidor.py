from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "d6c307de5c13"
down_revision: str | None = "dc2ff5819083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historial_pedido",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column("estado_desde", sa.String(length=24), nullable=False),
        sa.Column("estado_hacia", sa.String(length=24), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("nota", sa.String(length=512), nullable=True),
        sa.Column("tipo_incidencia", sa.String(length=32), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "estado_desde IN ('pendiente_pago', 'pagado', 'en_preparacion', 'despachado', 'en_reparto', 'entregado', 'incidencia', 'cancelado')",
            name="historial_estado_desde_valido",
        ),
        sa.CheckConstraint(
            "estado_hacia IN ('pendiente_pago', 'pagado', 'en_preparacion', 'despachado', 'en_reparto', 'entregado', 'incidencia', 'cancelado')",
            name="historial_estado_hacia_valido",
        ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_historial_pedido", "historial_pedido", ["pedido_id", "id"], unique=False)
    op.add_column("envio", sa.Column("repartidor_nombre", sa.String(length=128), nullable=True))
    op.add_column("envio", sa.Column("repartidor_celular", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "repartidor_celular")
    op.drop_column("envio", "repartidor_nombre")
    op.drop_index("ix_historial_pedido", table_name="historial_pedido")
    op.drop_table("historial_pedido")
