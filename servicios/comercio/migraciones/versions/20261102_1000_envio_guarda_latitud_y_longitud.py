from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "c7a41e9d02f5"
down_revision: str | None = "b619c58fc0c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("envio", sa.Column("latitud", sa.Float(), nullable=True))
    op.add_column("envio", sa.Column("longitud", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "longitud")
    op.drop_column("envio", "latitud")
