from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa
from alembic import op

revision: str = "3799d5a32ad7"
down_revision: str | None = "3abe3d8e2e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNAS = (
    ("logo_url", 1024),
    ("sitio_web", 512),
    ("contacto_nombre", 256),
    ("contacto_email", 256),
    ("contacto_telefono", 64),
    ("direccion", 512),
)


def upgrade() -> None:
    for nombre, largo in _COLUMNAS:
        op.add_column("colegio", sa.Column(nombre, sa.String(length=largo), nullable=True))


def downgrade() -> None:
    for nombre, _ in reversed(_COLUMNAS):
        op.drop_column("colegio", nombre)
