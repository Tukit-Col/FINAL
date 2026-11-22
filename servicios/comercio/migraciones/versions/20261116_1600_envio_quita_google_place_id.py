from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d3e8b52a7c19"
down_revision: str | None = "c7a41e9d02f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("envio") as lote:
        lote.drop_column("google_place_id")


def downgrade() -> None:
    with op.batch_alter_table("envio") as lote:
        lote.add_column(sa.Column("google_place_id", sa.String(length=512), nullable=True))
