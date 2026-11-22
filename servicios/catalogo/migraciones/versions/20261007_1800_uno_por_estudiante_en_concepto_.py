from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "8e2b7c4a9f13"
down_revision: str | None = "6d1a3f8c2e94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("concepto") as batch:
        batch.add_column(
            sa.Column("uno_por_estudiante", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("concepto") as batch:
        batch.drop_column("uno_por_estudiante")
