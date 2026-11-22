from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "82939e21610c"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bandeja_salida",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        "concepto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=False),
        sa.Column("nombre_canonico", sa.String(length=256), nullable=False),
        sa.Column(
            "sinonimos", sa.JSON().with_variant(postgresql.ARRAY(sa.String()), "postgresql"), nullable=False
        ),
        sa.Column("categoria", sa.String(length=64), nullable=False),
        sa.Column("tipo_item", sa.String(length=24), nullable=False),
        sa.Column(
            "atributos_requeridos",
            sa.JSON().with_variant(postgresql.ARRAY(sa.String()), "postgresql"),
            nullable=False,
        ),
        sa.Column("admite_personaje", sa.Boolean(), nullable=False),
        sa.Column("frecuencia_demanda", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "tipo_item IN ('util', 'texto', 'libro_libre', 'licencia_digital', 'no_comprar', 'diferido', 'uniforme', 'otro')",
            name="concepto_tipo_item_valido",
        ),
        sa.CheckConstraint("frecuencia_demanda >= 0", name="concepto_demanda_no_negativa"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_index("ix_concepto_categoria", "concepto", ["categoria"], unique=False)
    op.create_table(
        "configuracion_colegio_editorial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("dias_ventana_decision", sa.Integer(), nullable=False),
        sa.Column("politica_silencio", sa.String(length=32), nullable=False),
        sa.Column("exige_aprobacion_humana", sa.Boolean(), nullable=False),
        sa.Column("programa_predeterminado", sa.String(length=32), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "politica_silencio IN ('conservar_vigente', 'aceptar_propuesta', 'escalar')",
            name="config_politica_silencio_valida",
        ),
        sa.CheckConstraint("dias_ventana_decision > 0", name="config_ventana_positiva"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("colegio_id"),
    )
    op.create_table(
        "grupo_variante",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("representante_id", sa.Uuid(), nullable=True),
        sa.Column("criterio", sa.String(length=32), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "criterio IN ('ean', 'nombre_normalizado', 'manual')", name="grupo_criterio_valido"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "lista_oficial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("sede_id", sa.Uuid(), nullable=True),
        sa.Column("grado", sa.String(length=32), nullable=False),
        sa.Column("anio_lectivo", sa.Integer(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("colegio_id", "sede_id", "grado", "anio_lectivo", name="uq_lista_oficial"),
    )
    op.create_index("ix_lista_colegio", "lista_oficial", ["colegio_id", "anio_lectivo"], unique=False)
    op.create_table(
        "tienda",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("nombre", sa.String(length=256), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("url_base", sa.Text(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('minorista', 'mayorista', 'editorial', 'propia')", name="tienda_tipo_valido"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "concepto_ruta_categoria",
        sa.Column("concepto_id", sa.Uuid(), nullable=False),
        sa.Column("tienda_id", sa.Uuid(), nullable=False),
        sa.Column("ruta", sa.String(length=512), nullable=False),
        sa.Column("es_hoja", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["concepto_id"], ["concepto.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tienda_id"], ["tienda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("concepto_id", "tienda_id", "ruta"),
    )
    op.create_table(
        "corrida_scraper",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tienda_id", sa.Uuid(), nullable=False),
        sa.Column("iniciada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("terminada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("productos_vistos", sa.Integer(), nullable=False),
        sa.Column("errores", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('en_curso', 'completada', 'fallida', 'parcial')", name="corrida_estado_valido"
        ),
        sa.ForeignKeyConstraint(["tienda_id"], ["tienda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_corrida_tienda", "corrida_scraper", ["tienda_id", "iniciada_en"], unique=False)
    op.create_table(
        "producto_canonico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concepto_id", sa.Uuid(), nullable=False),
        sa.Column("ean", sa.String(length=14), nullable=True),
        sa.Column("sku_interno", sa.String(length=64), nullable=False),
        sa.Column("nombre", sa.String(length=512), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
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
        sa.Column("ruta_categoria", sa.Text(), nullable=True),
        sa.Column("es_propio", sa.Boolean(), nullable=False),
        sa.Column("grupo_variante_id", sa.Uuid(), nullable=True),
        sa.Column("es_representante_canonico", sa.Boolean(), nullable=False),
        sa.Column(
            "embedding",
            sa.JSON().with_variant(pgvector.sqlalchemy.vector.VECTOR(dim=1024), "postgresql"),
            nullable=True,
        ),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("texto_embedding", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("curado_por", sa.Uuid(), nullable=False),
        sa.Column("curado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("nivel IN ('economico', 'confiable', 'premium')", name="producto_nivel_valido"),
        sa.CheckConstraint(
            "unidad_base IN ('unidad', 'hoja', 'pliego', 'metro', 'gramo', 'mililitro')",
            name="producto_unidad_base_valida",
        ),
        sa.CheckConstraint("quality_score >= 0 AND quality_score <= 1", name="producto_calidad_en_rango"),
        sa.CheckConstraint("unidades_por_empaque > 0", name="producto_empaque_positivo"),
        sa.ForeignKeyConstraint(["concepto_id"], ["concepto.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["grupo_variante_id"], ["grupo_variante.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ean"),
        sa.UniqueConstraint("sku_interno"),
    )
    op.create_index(
        "ix_producto_concepto",
        "producto_canonico",
        ["concepto_id"],
        unique=False,
        postgresql_where=sa.text("activo"),
    )
    op.create_index("ix_producto_grupo", "producto_canonico", ["grupo_variante_id"], unique=False)
    op.create_index("ix_producto_nivel", "producto_canonico", ["concepto_id", "nivel"], unique=False)
    op.create_table(
        "sustituibilidad_concepto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concepto_origen_id", sa.Uuid(), nullable=False),
        sa.Column("concepto_sustituto_id", sa.Uuid(), nullable=False),
        sa.Column("grado", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("curado_por", sa.Uuid(), nullable=False),
        sa.Column("curado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "concepto_origen_id <> concepto_sustituto_id", name="sustituibilidad_no_reflexiva"
        ),
        sa.CheckConstraint("grado > 0 AND grado <= 1", name="sustituibilidad_grado_en_rango"),
        sa.ForeignKeyConstraint(["concepto_origen_id"], ["concepto.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concepto_sustituto_id"], ["concepto.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concepto_origen_id", "concepto_sustituto_id", name="uq_sustituibilidad_par"),
    )
    op.create_index(
        "ix_sustituibilidad_origen", "sustituibilidad_concepto", ["concepto_origen_id", "grado"], unique=False
    )
    op.create_table(
        "tarea_importacion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lista_id", sa.Uuid(), nullable=True),
        sa.Column("origen", sa.String(length=32), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("etapa_actual", sa.String(length=32), nullable=True),
        sa.Column("etapa_completada", sa.String(length=32), nullable=True),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actualizada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "estado <> 'fallida' OR error IS NOT NULL", name="tarea_fallida_tiene_diagnostico"
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'en_curso', 'completada', 'fallida', 'requiere_revision')",
            name="tarea_estado_valido",
        ),
        sa.CheckConstraint("intentos >= 0", name="tarea_intentos_no_negativos"),
        sa.ForeignKeyConstraint(["lista_id"], ["lista_oficial.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarea_pendiente", "tarea_importacion", ["estado", "actualizada_en"], unique=False)
    op.create_table(
        "version_lista_oficial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lista_id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("contenido_redactado", sa.Text(), nullable=True),
        sa.Column("hash_origen", sa.String(length=64), nullable=True),
        sa.Column(
            "publicada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("publicada_por", sa.Uuid(), nullable=True),
        sa.Column("vigente", sa.Boolean(), nullable=False),
        sa.CheckConstraint("numero > 0", name="version_numero_positivo"),
        sa.ForeignKeyConstraint(["lista_id"], ["lista_oficial.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lista_id", "numero", name="uq_version_lista_numero"),
    )
    op.create_index(
        "uq_version_lista_vigente",
        "version_lista_oficial",
        ["lista_id"],
        unique=True,
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.create_table(
        "edicion_libro",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("isbn13", sa.String(length=13), nullable=False),
        sa.Column("titulo", sa.String(length=512), nullable=False),
        sa.Column("editorial", sa.String(length=256), nullable=False),
        sa.Column("anio_edicion", sa.Integer(), nullable=False),
        sa.Column("numero_edicion", sa.String(length=32), nullable=True),
        sa.Column("area", sa.String(length=64), nullable=False),
        sa.Column("grado_sugerido", sa.String(length=32), nullable=True),
        sa.Column("programa", sa.String(length=32), nullable=False),
        sa.Column("descontinuada_en", sa.Date(), nullable=True),
        sa.Column("reemplazada_por_id", sa.Uuid(), nullable=True),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "programa IN ('nacional', 'bachillerato_internacional', 'cambridge', 'otro')",
            name="edicion_programa_valido",
        ),
        sa.CheckConstraint("anio_edicion >= 1980", name="edicion_anio_plausible"),
        sa.CheckConstraint(
            "reemplazada_por_id IS NULL OR reemplazada_por_id <> id",
            name="edicion_no_se_reemplaza_a_si_misma",
        ),
        sa.ForeignKeyConstraint(["producto_canonico_id"], ["producto_canonico.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reemplazada_por_id"], ["edicion_libro.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("isbn13"),
    )
    op.create_index("ix_edicion_area_programa", "edicion_libro", ["area", "programa"], unique=False)
    op.create_table(
        "item_lista_oficial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("texto_original", sa.Text(), nullable=False),
        sa.Column("concepto_id", sa.Uuid(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("unidad", sa.String(length=16), nullable=True),
        sa.Column("tipo_item", sa.String(length=24), nullable=True),
        sa.Column("modo_adquisicion", sa.String(length=32), nullable=False),
        sa.Column("instruccion_colegio", sa.Text(), nullable=True),
        sa.Column("url_externa", sa.Text(), nullable=True),
        sa.Column(
            "atributos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("confianza_normalizacion", sa.Float(), nullable=True),
        sa.Column("requiere_revision", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "modo_adquisicion IN ('libro_libre', 'mercado_abierto') OR instruccion_colegio IS NOT NULL",
            name="item_no_surtible_explica_como_conseguirlo",
        ),
        sa.CheckConstraint(
            "modo_adquisicion IN ('mercado_abierto', 'libro_libre', 'venta_directa_editorial', 'edicion_exclusiva', 'plataforma', 'diferido')",
            name="item_modo_adquisicion_valido",
        ),
        sa.CheckConstraint(
            "tipo_item IS NULL OR tipo_item IN ('util', 'texto', 'libro_libre', 'licencia_digital', 'no_comprar', 'diferido', 'uniforme', 'otro')",
            name="item_tipo_item_valido",
        ),
        sa.CheckConstraint(
            "unidad IS NULL OR unidad IN ('unidad', 'hoja', 'pliego', 'metro', 'gramo', 'mililitro')",
            name="item_unidad_valida",
        ),
        sa.CheckConstraint("cantidad > 0", name="item_cantidad_positiva"),
        sa.CheckConstraint(
            "concepto_id IS NOT NULL OR requiere_revision", name="item_sin_concepto_va_a_revision"
        ),
        sa.ForeignKeyConstraint(["concepto_id"], ["concepto.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["version_id"], ["version_lista_oficial.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "orden", name="uq_item_version_orden"),
    )
    op.create_index("ix_item_concepto", "item_lista_oficial", ["concepto_id"], unique=False)
    op.create_table(
        "oferta_tienda",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_canonico_id", sa.Uuid(), nullable=False),
        sa.Column("tienda_id", sa.Uuid(), nullable=False),
        sa.Column("referencia_externa", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("metodo_vinculacion", sa.String(length=16), nullable=False),
        sa.Column("confianza_vinculacion", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("disponible", sa.Boolean(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("visto_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "metodo_vinculacion IN ('ean', 'atributos', 'manual')", name="oferta_metodo_valido"
        ),
        sa.CheckConstraint(
            "confianza_vinculacion >= 0 AND confianza_vinculacion <= 1", name="oferta_confianza_en_rango"
        ),
        sa.ForeignKeyConstraint(["producto_canonico_id"], ["producto_canonico.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tienda_id"], ["tienda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("producto_canonico_id", "tienda_id", name="uq_oferta_producto_tienda"),
        sa.UniqueConstraint("tienda_id", "referencia_externa", name="uq_oferta_referencia"),
    )
    op.create_index(
        "ix_oferta_producto",
        "oferta_tienda",
        ["producto_canonico_id"],
        unique=False,
        postgresql_where=sa.text("activo"),
    )
    op.create_index(
        "ix_oferta_revision_manual",
        "oferta_tienda",
        ["confianza_vinculacion"],
        unique=False,
        postgresql_where=sa.text("metodo_vinculacion = 'atributos' AND confianza_vinculacion < 0.8"),
        sqlite_where=sa.text("metodo_vinculacion = 'atributos' AND confianza_vinculacion < 0.8"),
    )
    op.create_table(
        "precio_oferta",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("oferta_id", sa.Uuid(), nullable=False),
        sa.Column("valor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column("fuente", sa.String(length=16), nullable=False),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrida_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("fuente IN ('scraper', 'manual', 'referencia')", name="precio_fuente_valida"),
        sa.CheckConstraint("moneda IN ('COP')", name="precio_moneda_valida"),
        sa.CheckConstraint("valor_centavos >= 0", name="precio_no_negativo"),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="precio_vigencia_coherente"
        ),
        sa.ForeignKeyConstraint(["corrida_id"], ["corrida_scraper.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["oferta_id"], ["oferta_tienda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_precio_oferta_historial", "precio_oferta", ["oferta_id", "vigente_desde"], unique=False
    )
    op.create_index(
        "uq_precio_vigente_por_oferta",
        "precio_oferta",
        ["oferta_id"],
        unique=True,
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.create_table(
        "propuesta_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("edicion_propuesta_id", sa.Uuid(), nullable=False),
        sa.Column("edicion_actual_id", sa.Uuid(), nullable=True),
        sa.Column("area", sa.String(length=64), nullable=False),
        sa.Column("grado", sa.String(length=32), nullable=False),
        sa.Column("anio_lectivo", sa.Integer(), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.Column("delta_precio_centavos", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("recibida_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("vence_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resuelta_por", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(estado IN ('pendiente', 'vencida')) OR (resuelta_en IS NOT NULL AND resuelta_por IS NOT NULL)",
            name="propuesta_resuelta_tiene_responsable",
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aceptada', 'rechazada', 'vencida')", name="propuesta_estado_valido"
        ),
        sa.CheckConstraint(
            "edicion_actual_id IS NULL OR edicion_actual_id <> edicion_propuesta_id",
            name="propuesta_cambia_de_edicion",
        ),
        sa.CheckConstraint("vence_en > recibida_en", name="propuesta_ventana_coherente"),
        sa.ForeignKeyConstraint(["edicion_actual_id"], ["edicion_libro.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["edicion_propuesta_id"], ["edicion_libro.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "colegio_id",
            "area",
            "grado",
            "anio_lectivo",
            "edicion_propuesta_id",
            name="uq_propuesta_sin_duplicar",
        ),
    )
    op.create_index(
        "ix_propuesta_por_vencer",
        "propuesta_version",
        ["vence_en"],
        unique=False,
        postgresql_where=sa.text("estado = 'pendiente'"),
        sqlite_where=sa.text("estado = 'pendiente'"),
    )
    op.create_table(
        "version_vigente",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("edicion_id", sa.Uuid(), nullable=False),
        sa.Column("area", sa.String(length=64), nullable=False),
        sa.Column("grado", sa.String(length=32), nullable=False),
        sa.Column("anio_lectivo", sa.Integer(), nullable=False),
        sa.Column(
            "vigente_desde", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="version_vigencia_coherente"
        ),
        sa.ForeignKeyConstraint(["edicion_id"], ["edicion_libro.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_version_vigente_actual",
        "version_vigente",
        ["colegio_id", "area", "grado", "anio_lectivo"],
        unique=True,
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )

    op.create_foreign_key(
        "fk_grupo_variante_representante",
        "grupo_variante",
        "producto_canonico",
        ["representante_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_grupo_variante_representante", "grupo_variante", type_="foreignkey")
    op.drop_index(
        "uq_version_vigente_actual",
        table_name="version_vigente",
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.drop_table("version_vigente")
    op.drop_index(
        "ix_propuesta_por_vencer",
        table_name="propuesta_version",
        postgresql_where=sa.text("estado = 'pendiente'"),
        sqlite_where=sa.text("estado = 'pendiente'"),
    )
    op.drop_table("propuesta_version")
    op.drop_index(
        "uq_precio_vigente_por_oferta",
        table_name="precio_oferta",
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.drop_index("ix_precio_oferta_historial", table_name="precio_oferta")
    op.drop_table("precio_oferta")
    op.drop_index(
        "ix_oferta_revision_manual",
        table_name="oferta_tienda",
        postgresql_where=sa.text("metodo_vinculacion = 'atributos' AND confianza_vinculacion < 0.8"),
        sqlite_where=sa.text("metodo_vinculacion = 'atributos' AND confianza_vinculacion < 0.8"),
    )
    op.drop_index("ix_oferta_producto", table_name="oferta_tienda", postgresql_where=sa.text("activo"))
    op.drop_table("oferta_tienda")
    op.drop_index("ix_item_concepto", table_name="item_lista_oficial")
    op.drop_table("item_lista_oficial")
    op.drop_index("ix_edicion_area_programa", table_name="edicion_libro")
    op.drop_table("edicion_libro")
    op.drop_index(
        "uq_version_lista_vigente",
        table_name="version_lista_oficial",
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.drop_table("version_lista_oficial")
    op.drop_index("ix_tarea_pendiente", table_name="tarea_importacion")
    op.drop_table("tarea_importacion")
    op.drop_index("ix_sustituibilidad_origen", table_name="sustituibilidad_concepto")
    op.drop_table("sustituibilidad_concepto")
    op.drop_index("ix_producto_nivel", table_name="producto_canonico")
    op.drop_index("ix_producto_grupo", table_name="producto_canonico")
    op.drop_index("ix_producto_concepto", table_name="producto_canonico", postgresql_where=sa.text("activo"))
    op.drop_table("producto_canonico")
    op.drop_index("ix_corrida_tienda", table_name="corrida_scraper")
    op.drop_table("corrida_scraper")
    op.drop_table("concepto_ruta_categoria")
    op.drop_table("tienda")
    op.drop_index("ix_lista_colegio", table_name="lista_oficial")
    op.drop_table("lista_oficial")
    op.drop_table("grupo_variante")
    op.drop_table("configuracion_colegio_editorial")
    op.drop_index("ix_concepto_categoria", table_name="concepto")
    op.drop_table("concepto")
    op.drop_index(
        "ix_bandeja_salida_pendiente",
        table_name="bandeja_salida",
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.drop_table("bandeja_salida")
