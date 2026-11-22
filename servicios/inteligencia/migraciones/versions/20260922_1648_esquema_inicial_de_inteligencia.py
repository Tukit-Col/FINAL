from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401
from sqlalchemy.dialects import postgresql

revision: str = "fa6f12dd724e"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bandeja_salida",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
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
        sa.Column("intentos", sa.Integer(), nullable=False),
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
        "trabajo_pipeline",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("origen", sa.String(length=24), nullable=False),
        sa.Column(
            "hijos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("preferencias_cifradas", sa.LargeBinary(), nullable=True),
        sa.Column("estimado_segundos", sa.Integer(), nullable=False),
        sa.Column(
            "degradaciones",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("error", sa.String(length=64), nullable=True),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("revisado_por", sa.Uuid(), nullable=True),
        sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nota_revision", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("terminado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado <> 'fallido' OR error IS NOT NULL", name="trabajo_fallido_tiene_diagnostico"
        ),
        sa.CheckConstraint(
            "estado IN ('encolado', 'procesando', 'espera_revision', 'publicado', 'fallido')",
            name="trabajo_estado_valido",
        ),
        sa.CheckConstraint("origen IN ('colegio_grado', 'archivo')", name="trabajo_origen_valido"),
        sa.CheckConstraint("estimado_segundos > 0", name="trabajo_estimado_positivo"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trabajo_en_cola",
        "trabajo_pipeline",
        ["creado_en"],
        unique=False,
        postgresql_where=sa.text("estado = 'espera_revision'"),
        sqlite_where=sa.text("estado = 'espera_revision'"),
    )
    op.create_index("ix_trabajo_usuario", "trabajo_pipeline", ["usuario_id", "creado_en"], unique=False)
    op.create_table(
        "etapa_trabajo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trabajo_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=32), nullable=False),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=True),
        sa.Column(
            "detalle",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("iniciada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'ok', 'degradada', 'fallida', 'omitida')", name="etapa_estado_valido"
        ),
        sa.CheckConstraint("ms IS NULL OR ms >= 0", name="etapa_ms_no_negativo"),
        sa.ForeignKeyConstraint(["trabajo_id"], ["trabajo_pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trabajo_id", "nombre", name="uq_etapa_trabajo"),
    )
    op.create_index("ix_etapa_trabajo", "etapa_trabajo", ["trabajo_id"], unique=False)
    op.create_table(
        "item_crudo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trabajo_id", sa.Uuid(), nullable=False),
        sa.Column("matricula_id", sa.Uuid(), nullable=True),
        sa.Column("hijo_referencia", sa.String(length=64), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("unidad_base", sa.String(length=16), nullable=False),
        sa.Column("unidades_por_empaque", sa.Integer(), nullable=True),
        sa.Column("tipo_item", sa.String(length=24), nullable=False),
        sa.Column("modo_adquisicion", sa.String(length=32), nullable=False),
        sa.Column("instruccion_colegio", sa.Text(), nullable=True),
        sa.Column("url_externa", sa.Text(), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("confianza_extraccion", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("cantidad >= 0", name="item_crudo_cantidad_no_negativa"),
        sa.CheckConstraint(
            "unidades_por_empaque IS NULL OR unidades_por_empaque > 0", name="item_crudo_empaque_positivo"
        ),
        sa.ForeignKeyConstraint(["trabajo_id"], ["trabajo_pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trabajo_id", "hijo_referencia", "orden", name="uq_item_crudo_orden"),
    )
    op.create_index(
        "ix_item_crudo_trabajo", "item_crudo", ["trabajo_id", "hijo_referencia", "orden"], unique=False
    )
    op.create_table(
        "kit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trabajo_id", sa.Uuid(), nullable=False),
        sa.Column("matricula_id", sa.Uuid(), nullable=True),
        sa.Column("perfil", sa.String(length=16), nullable=False),
        sa.Column("total_cop", sa.Integer(), nullable=False),
        sa.Column(
            "objetivos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("recomendado", sa.Boolean(), nullable=False),
        sa.Column("razon_recomendacion", sa.Text(), nullable=True),
        sa.Column("dentro_de_presupuesto", sa.Boolean(), nullable=True),
        sa.Column("pesos_usados_cifrados", sa.LargeBinary(), nullable=True),
        sa.Column(
            "consolidaciones",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint("perfil IN ('Ahorrador', 'Fan', 'Premium')", name="kit_perfil_valido"),
        sa.CheckConstraint("total_cop >= 0", name="kit_total_no_negativo"),
        sa.ForeignKeyConstraint(["trabajo_id"], ["trabajo_pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trabajo_id", "perfil", name="uq_kit_trabajo_perfil"),
    )
    op.create_index("ix_kit_trabajo", "kit", ["trabajo_id"], unique=False)
    op.create_table(
        "candidato_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_crudo_id", sa.Uuid(), nullable=False),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("nombre", sa.String(length=512), nullable=False),
        sa.Column("marca", sa.String(length=128), nullable=True),
        sa.Column("nivel", sa.String(length=16), nullable=False),
        sa.Column("personaje", sa.String(length=64), nullable=True),
        sa.Column("imagen_url", sa.Text(), nullable=True),
        sa.Column("unidad_base", sa.String(length=16), nullable=False),
        sa.Column("unidades_por_empaque", sa.Integer(), nullable=False),
        sa.Column(
            "atributos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("precio_cop", sa.Integer(), nullable=True),
        sa.Column("confianza", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("cumple_atributos", sa.Boolean(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.CheckConstraint("confianza >= 0 AND confianza <= 1", name="candidato_confianza_en_rango"),
        sa.CheckConstraint("precio_cop IS NULL OR precio_cop >= 0", name="candidato_precio_no_negativo"),
        sa.CheckConstraint("unidades_por_empaque > 0", name="candidato_empaque_positivo"),
        sa.ForeignKeyConstraint(["item_crudo_id"], ["item_crudo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_crudo_id", "sku", name="uq_candidato_item_sku"),
    )
    op.create_index("ix_candidato_item", "candidato_item", ["item_crudo_id", "orden"], unique=False)
    op.create_table(
        "linea_kit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kit_id", sa.Uuid(), nullable=False),
        sa.Column("item_crudo_id", sa.Uuid(), nullable=False),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=True),
        sa.Column("hijo_referencia", sa.String(length=64), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("tipo", sa.String(length=24), nullable=False),
        sa.Column("estado_resolucion", sa.String(length=24), nullable=False),
        sa.Column("cantidad_pedida", sa.Integer(), nullable=False),
        sa.Column("unidad_base", sa.String(length=16), nullable=False),
        sa.Column("unidades_por_empaque", sa.Integer(), nullable=False),
        sa.Column("unidades_a_comprar", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("nombre_producto", sa.String(length=512), nullable=True),
        sa.Column("marca", sa.String(length=128), nullable=True),
        sa.Column("nivel", sa.String(length=16), nullable=True),
        sa.Column("personaje", sa.String(length=64), nullable=True),
        sa.Column("imagen_url", sa.Text(), nullable=True),
        sa.Column("confianza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("precio_unitario_cop", sa.Integer(), nullable=True),
        sa.Column("subtotal_cop", sa.Integer(), nullable=True),
        sa.Column("informativa", sa.Boolean(), nullable=False),
        sa.Column("instruccion_colegio", sa.Text(), nullable=True),
        sa.Column("url_externa", sa.Text(), nullable=True),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("no_consolidable", sa.Boolean(), nullable=False),
        sa.Column("motivo_no_consolidable", sa.Text(), nullable=True),
        sa.Column(
            "alternativas",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "sustitutos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estado_resolucion IN ('RESUELTO_AUTO', 'AMBIGUO', 'SIN_MATCH', 'HUECO_CATALOGO')",
            name="linea_estado_valido",
        ),
        sa.CheckConstraint(
            "NOT informativa OR (precio_unitario_cop IS NULL AND subtotal_cop IS NULL)",
            name="linea_informativa_sin_precio",
        ),
        sa.CheckConstraint("cantidad_pedida >= 0", name="linea_cantidad_no_negativa"),
        sa.CheckConstraint("unidades_a_comprar >= 0", name="linea_unidades_no_negativas"),
        sa.CheckConstraint("unidades_por_empaque > 0", name="linea_empaque_positivo"),
        sa.ForeignKeyConstraint(["item_crudo_id"], ["item_crudo.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kit_id"], ["kit.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kit_id", "hijo_referencia", "orden", name="uq_linea_kit_orden"),
    )
    op.create_index("ix_linea_kit", "linea_kit", ["kit_id", "hijo_referencia", "orden"], unique=False)
    op.create_table(
        "resolucion_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_crudo_id", sa.Uuid(), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("concepto_codigo", sa.String(length=64), nullable=True),
        sa.Column("concepto_nombre", sa.String(length=256), nullable=True),
        sa.Column("parecido", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("candidato_item_id", sa.Uuid(), nullable=True),
        sa.Column(
            "atributos_impuestos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("decidido_por", sa.Uuid(), nullable=True),
        sa.Column("decidido_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado <> 'RESUELTO_AUTO' OR candidato_item_id IS NOT NULL",
            name="resolucion_resuelta_tiene_candidato",
        ),
        sa.CheckConstraint(
            "estado IN ('RESUELTO_AUTO', 'AMBIGUO', 'SIN_MATCH', 'HUECO_CATALOGO')",
            name="resolucion_estado_valido",
        ),
        sa.CheckConstraint("parecido >= 0 AND parecido <= 1", name="resolucion_parecido_en_rango"),
        sa.ForeignKeyConstraint(["candidato_item_id"], ["candidato_item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_crudo_id"], ["item_crudo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_crudo_id"),
    )
    op.create_index("ix_resolucion_estado", "resolucion_item", ["estado"], unique=False)
    op.create_table(
        "transicion_resolucion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resolucion_item_id", sa.Uuid(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=24), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=24), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("decidida_por", sa.Uuid(), nullable=True),
        sa.Column("ocurrida_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "estado_anterior IS NULL OR estado_anterior IN ('RESUELTO_AUTO', 'AMBIGUO', 'SIN_MATCH', 'HUECO_CATALOGO')",
            name="transicion_estado_anterior_valido",
        ),
        sa.CheckConstraint(
            "estado_nuevo IN ('RESUELTO_AUTO', 'AMBIGUO', 'SIN_MATCH', 'HUECO_CATALOGO')",
            name="transicion_estado_nuevo_valido",
        ),
        sa.ForeignKeyConstraint(["resolucion_item_id"], ["resolucion_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transicion_resolucion",
        "transicion_resolucion",
        ["resolucion_item_id", "ocurrida_en"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transicion_resolucion", table_name="transicion_resolucion")
    op.drop_table("transicion_resolucion")
    op.drop_index("ix_resolucion_estado", table_name="resolucion_item")
    op.drop_table("resolucion_item")
    op.drop_index("ix_linea_kit", table_name="linea_kit")
    op.drop_table("linea_kit")
    op.drop_index("ix_candidato_item", table_name="candidato_item")
    op.drop_table("candidato_item")
    op.drop_index("ix_kit_trabajo", table_name="kit")
    op.drop_table("kit")
    op.drop_index("ix_item_crudo_trabajo", table_name="item_crudo")
    op.drop_table("item_crudo")
    op.drop_index("ix_etapa_trabajo", table_name="etapa_trabajo")
    op.drop_table("etapa_trabajo")
    op.drop_index("ix_trabajo_usuario", table_name="trabajo_pipeline")
    op.drop_index(
        "ix_trabajo_en_cola",
        table_name="trabajo_pipeline",
        postgresql_where=sa.text("estado = 'espera_revision'"),
        sqlite_where=sa.text("estado = 'espera_revision'"),
    )
    op.drop_table("trabajo_pipeline")
    op.drop_index(
        "ix_bandeja_salida_pendiente",
        table_name="bandeja_salida",
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.drop_table("bandeja_salida")
