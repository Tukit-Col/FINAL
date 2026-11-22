from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c1e8a3f9b20"
down_revision: str | None = "3f7b9e2d4c18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.add_column(
            sa.Column(
                "cambios",
                sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_column("cambios")
