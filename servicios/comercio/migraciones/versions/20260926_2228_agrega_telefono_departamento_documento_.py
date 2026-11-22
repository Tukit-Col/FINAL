from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "dc2ff5819083"
down_revision: str | None = "bf13445a1ec8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("envio", sa.Column("telefono", sa.String(length=32), nullable=True))
    op.add_column("envio", sa.Column("departamento", sa.String(length=128), nullable=True))
    op.add_column("envio", sa.Column("documento_destinatario", sa.String(length=64), nullable=True))
    op.add_column("envio", sa.Column("indicaciones", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "indicaciones")
    op.drop_column("envio", "documento_destinatario")
    op.drop_column("envio", "departamento")
    op.drop_column("envio", "telefono")
