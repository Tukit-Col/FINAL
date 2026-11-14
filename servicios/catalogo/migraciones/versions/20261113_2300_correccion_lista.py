"""correccion_lista: lo que el equipo corrige en la cola, con antes y despues

Revision: 9e3c5a7b1f42
Anterior: 7b4e2a9c1d36
Fecha:    2026-11-13 23:00:00.000000+00:00

Por que este cambio: las correcciones de la cola de revision se quedaban solo en
la fila corregida; el sistema no tenia de donde aprender y el mismo texto volvia a
fallar en otro colegio. Esta tabla guarda cada correccion (campo, antes, despues,
texto, autor y fecha) y lo que el sistema aprendio con ella.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e3c5a7b1f42"
down_revision: str | None = "7b4e2a9c1d36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "correccion_lista",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("campo", sa.String(24), nullable=False),
        sa.Column("valor_antes", sa.JSON(), nullable=True),
        sa.Column("valor_despues", sa.JSON(), nullable=True),
        sa.Column("texto_original", sa.Text(), nullable=True),
        sa.Column("aprendido", sa.JSON(), nullable=True),
        sa.Column("actor", sa.Uuid(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_correccion_lista_version", "correccion_lista", ["version_id"])
    op.create_index("ix_correccion_lista_creado", "correccion_lista", ["creado_en"])


def downgrade() -> None:
    op.drop_index("ix_correccion_lista_creado", table_name="correccion_lista")
    op.drop_index("ix_correccion_lista_version", table_name="correccion_lista")
    op.drop_table("correccion_lista")
