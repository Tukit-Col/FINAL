from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "9f3c8d5b1a24"
down_revision: str | None = "8e2b7c4a9f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("item_lista_oficial") as batch:
        batch.add_column(
            sa.Column(
                "avisos_descartados",
                sa.JSON().with_variant(JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("item_lista_oficial") as batch:
        batch.drop_column("avisos_descartados")
