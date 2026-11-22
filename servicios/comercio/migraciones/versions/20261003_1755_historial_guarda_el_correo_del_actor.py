from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "a58b45f8b14c"
down_revision: str | None = "d6c307de5c13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("historial_pedido", sa.Column("actor_correo", sa.String(length=320), nullable=True))


def downgrade() -> None:
    op.drop_column("historial_pedido", "actor_correo")
