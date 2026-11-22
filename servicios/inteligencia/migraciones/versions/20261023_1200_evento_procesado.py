from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c7d9e1f5a28"
down_revision: str | None = "6a2f8c4e1d57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evento_procesado",
        sa.Column("origen", sa.String(length=32), nullable=False),
        sa.Column("evento_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("origen", "evento_id"),
    )


def downgrade() -> None:
    op.drop_table("evento_procesado")
