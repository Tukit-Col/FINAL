from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "79d641af049e"
down_revision: str | None = "7c679f269235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "version_lista_oficial", sa.Column("revisada_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("version_lista_oficial", sa.Column("revisada_por", sa.Uuid(), nullable=True))

    op.add_column(
        "propuesta_producto",
        sa.Column("origen", sa.String(length=16), nullable=False, server_default="scraper"),
    )
    op.alter_column("propuesta_producto", "origen", server_default=None)
    op.create_check_constraint(
        "propuesta_origen_valido", "propuesta_producto", "origen IN ('scraper', 'manual')"
    )

    op.add_column("propuesta_producto", sa.Column("version_lista_id", sa.Uuid(), nullable=True))
    op.add_column("propuesta_producto", sa.Column("item_lista_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_propuesta_version_lista",
        "propuesta_producto",
        "version_lista_oficial",
        ["version_lista_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_propuesta_item_lista",
        "propuesta_producto",
        "item_lista_oficial",
        ["item_lista_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_propuesta_item_lista", "propuesta_producto", type_="foreignkey")
    op.drop_constraint("fk_propuesta_version_lista", "propuesta_producto", type_="foreignkey")
    op.drop_column("propuesta_producto", "item_lista_id")
    op.drop_column("propuesta_producto", "version_lista_id")
    op.drop_constraint("propuesta_origen_valido", "propuesta_producto", type_="check")
    op.drop_column("propuesta_producto", "origen")
    op.drop_column("version_lista_oficial", "revisada_por")
    op.drop_column("version_lista_oficial", "revisada_en")
