from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "a91c5e7d2b40"
down_revision: str | None = "3f0bbbca4e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notificacion") as batch:
        batch.add_column(sa.Column("asunto", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("detalle", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("destino_dominio", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notificacion") as batch:
        batch.drop_column("destino_dominio")
        batch.drop_column("detalle")
        batch.drop_column("asunto")
