"""tabla importacion_lista

Revision: 6a2f8c4e1d57
Anterior: 9e3a5f7b2c41
Fecha:    2026-10-19 12:00:00.000000+00:00

Por que este cambio: con el catalogo caido, `POST /v1/listas/subir` respondia
500 y la lista ya percibida se perdia (H-B-01). La subida deja ahora lo
percibido en `importacion_lista` antes de llamar al catalogo; si el catalogo no
responde, la fila queda `pendiente` y el trabajador la importa cuando vuelve,
con una clave de idempotencia por subida y destino (ADR 0040).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6a2f8c4e1d57"
down_revision: str | None = "9e3a5f7b2c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "importacion_lista",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subida_id", sa.Uuid(), nullable=False),
        sa.Column("clave_idempotencia", sa.Uuid(), nullable=False),
        sa.Column("referencias", _JSON, nullable=False),
        sa.Column("contacto_referencia", sa.String(length=64), nullable=True),
        sa.Column("colegio_id", sa.String(length=64), nullable=False),
        sa.Column("grado", sa.String(length=64), nullable=False),
        sa.Column("anio_lectivo", sa.Integer(), nullable=False),
        sa.Column("carga", _JSON, nullable=True),
        sa.Column("documento", sa.LargeBinary(), nullable=True),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("proximo_intento_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'importada', 'fallida')", name="importacion_estado_valido"
        ),
        sa.CheckConstraint(
            "estado <> 'fallida' OR error IS NOT NULL", name="importacion_fallida_tiene_diagnostico"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clave_idempotencia", name="uq_importacion_clave"),
    )
    op.create_index(
        "ix_importacion_pendiente",
        "importacion_lista",
        ["proximo_intento_en"],
        unique=False,
        postgresql_where=sa.text("estado = 'pendiente'"),
        sqlite_where=sa.text("estado = 'pendiente'"),
    )
    op.create_index(
        "ix_importacion_contacto", "importacion_lista", ["contacto_referencia", "creado_en"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_importacion_contacto", table_name="importacion_lista")
    op.drop_index("ix_importacion_pendiente", table_name="importacion_lista")
    op.drop_table("importacion_lista")
