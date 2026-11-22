from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "7b4e2a9c1d36"
down_revision: str | None = "5c1d8e2f7a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("referencias", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("referencias")
