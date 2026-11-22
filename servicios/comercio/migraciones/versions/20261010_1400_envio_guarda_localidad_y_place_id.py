from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "b619c58fc0c3"
down_revision: str | None = "a58b45f8b14c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("envio", sa.Column("localidad", sa.String(length=64), nullable=True))
    op.add_column("envio", sa.Column("google_place_id", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "google_place_id")
    op.drop_column("envio", "localidad")
