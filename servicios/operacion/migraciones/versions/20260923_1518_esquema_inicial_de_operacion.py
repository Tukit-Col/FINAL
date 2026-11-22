from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401
from sqlalchemy.dialects import postgresql

revision: str = "d0bf03671b97"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bandeja_salida",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("tipo", sa.String(length=128), nullable=False),
        sa.Column("agregado_tipo", sa.String(length=64), nullable=False),
        sa.Column("agregado_id", sa.Uuid(), nullable=False),
        sa.Column(
            "carga",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bandeja_salida_pendiente",
        "bandeja_salida",
        ["creado_en"],
        unique=False,
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.create_table(
        "caso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("origen", sa.String(length=16), nullable=False),
        sa.Column("categoria", sa.String(length=24), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("prioridad", sa.String(length=16), nullable=False),
        sa.Column("asunto", sa.String(length=256), nullable=False),
        sa.Column("descripcion", sa.String(length=4096), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("trabajo_id", sa.Uuid(), nullable=True),
        sa.Column("pedido_id", sa.Uuid(), nullable=True),
        sa.Column("asignado_a_id", sa.Uuid(), nullable=True),
        sa.Column("abierto_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("vence_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "categoria IN ('pago', 'stock', 'entrega', 'mapeo_lista', 'autenticacion', 'peticion', 'queja', 'reclamo', 'sugerencia')",
            name="caso_categoria_valida",
        ),
        sa.CheckConstraint(
            "estado IN ('abierto', 'en_gestion', 'esperando_tercero', 'resuelto', 'cerrado')",
            name="caso_estado_valido",
        ),
        sa.CheckConstraint(
            "origen IN ('acudiente', 'colegio', 'operador', 'sistema')", name="caso_origen_valido"
        ),
        sa.CheckConstraint("prioridad IN ('urgente', 'alta', 'media', 'baja')", name="caso_prioridad_valida"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_caso_asignado", "caso", ["asignado_a_id"], unique=False)
    op.create_index("ix_caso_estado", "caso", ["estado"], unique=False)
    op.create_index("ix_caso_prioridad_vence", "caso", ["prioridad", "vence_en"], unique=False)
    op.create_index("ix_caso_usuario", "caso", ["usuario_id"], unique=False)
    op.create_table(
        "evento_clickout",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kit_id", sa.Uuid(), nullable=False),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=False),
        sa.Column("tienda", sa.String(length=128), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clickout_kit", "evento_clickout", ["kit_id"], unique=False)
    op.create_index("ix_clickout_producto", "evento_clickout", ["producto_canonico_id"], unique=False)
    op.create_table(
        "metrica_diaria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("dimension_id", sa.String(length=128), nullable=True),
        sa.Column("metrica", sa.String(length=64), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fecha", "dimension", "dimension_id", "metrica", name="uq_metrica_diaria"),
    )
    op.create_index(
        "ix_metrica_dimension", "metrica_diaria", ["dimension", "dimension_id", "fecha"], unique=False
    )
    op.create_table(
        "notificacion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("canal", sa.String(length=16), nullable=False),
        sa.Column("plantilla", sa.String(length=64), nullable=False),
        sa.Column(
            "datos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("enviada_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notificacion_estado", "notificacion", ["estado"], unique=False)
    op.create_index("ix_notificacion_usuario", "notificacion", ["usuario_id"], unique=False)
    op.create_table(
        "preferencia_notificacion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("acepta_correo", sa.Boolean(), nullable=False),
        sa.Column("acepta_wa_link", sa.Boolean(), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id"),
    )
    op.create_index("ix_preferencia_usuario", "preferencia_notificacion", ["usuario_id"], unique=False)
    op.create_table(
        "registro_auditoria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("accion", sa.String(length=64), nullable=False),
        sa.Column("agregado_tipo", sa.String(length=64), nullable=False),
        sa.Column("agregado_id", sa.String(length=128), nullable=False),
        sa.Column(
            "datos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditoria_actor", "registro_auditoria", ["actor_id"], unique=False)
    op.create_index(
        "ix_auditoria_agregado", "registro_auditoria", ["agregado_tipo", "agregado_id"], unique=False
    )
    op.create_table(
        "alarma",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("caso_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("dispara_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["caso_id"], ["caso.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alarma_caso", "alarma", ["caso_id", "activa"], unique=False)
    op.create_table(
        "evento_caso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("caso_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column(
            "datos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["caso_id"], ["caso.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evento_caso", "evento_caso", ["caso_id", "creado_en"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evento_caso", table_name="evento_caso")
    op.drop_table("evento_caso")
    op.drop_index("ix_alarma_caso", table_name="alarma")
    op.drop_table("alarma")
    op.drop_index("ix_auditoria_agregado", table_name="registro_auditoria")
    op.drop_index("ix_auditoria_actor", table_name="registro_auditoria")
    op.drop_table("registro_auditoria")
    op.drop_index("ix_preferencia_usuario", table_name="preferencia_notificacion")
    op.drop_table("preferencia_notificacion")
    op.drop_index("ix_notificacion_usuario", table_name="notificacion")
    op.drop_index("ix_notificacion_estado", table_name="notificacion")
    op.drop_table("notificacion")
    op.drop_index("ix_metrica_dimension", table_name="metrica_diaria")
    op.drop_table("metrica_diaria")
    op.drop_index("ix_clickout_producto", table_name="evento_clickout")
    op.drop_index("ix_clickout_kit", table_name="evento_clickout")
    op.drop_table("evento_clickout")
    op.drop_index("ix_caso_usuario", table_name="caso")
    op.drop_index("ix_caso_prioridad_vence", table_name="caso")
    op.drop_index("ix_caso_estado", table_name="caso")
    op.drop_index("ix_caso_asignado", table_name="caso")
    op.drop_table("caso")
    op.drop_index(
        "ix_bandeja_salida_pendiente",
        table_name="bandeja_salida",
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.drop_table("bandeja_salida")
