from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d9a1c7e2b58"
down_revision: str | None = "8b2e4d6f0a13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "apodo_subida",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("referencia", sa.String(length=64), nullable=False),
        sa.Column("contacto_referencia", sa.String(length=64), nullable=True),
        sa.Column("apodo_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apodo_subida_version_id", "apodo_subida", ["version_id"])
    op.create_index("ix_apodo_subida_contacto_referencia", "apodo_subida", ["contacto_referencia"])


def downgrade() -> None:
    op.drop_index("ix_apodo_subida_contacto_referencia", table_name="apodo_subida")
    op.drop_index("ix_apodo_subida_version_id", table_name="apodo_subida")
    op.drop_table("apodo_subida")
