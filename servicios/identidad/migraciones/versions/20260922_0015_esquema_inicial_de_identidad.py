from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3abe3d8e2e31"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bandeja_salida",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tipo_evento", sa.String(length=128), nullable=False),
        sa.Column("clave_agregado", sa.String(length=128), nullable=False),
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
        "ix_bandeja_pendiente",
        "bandeja_salida",
        ["creado_en"],
        unique=False,
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.create_table(
        "colegio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=256), nullable=False),
        sa.Column("nit", sa.String(length=32), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nit"),
    )
    op.create_table(
        "estudiante",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("documento_hash", sa.LargeBinary(), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_estudiante_documento",
        "estudiante",
        ["documento_hash"],
        unique=True,
        postgresql_where=sa.text("documento_hash IS NOT NULL"),
        sqlite_where=sa.text("documento_hash IS NOT NULL"),
    )
    op.create_table(
        "permiso",
        sa.Column("codigo", sa.String(length=128), nullable=False),
        sa.Column("recurso", sa.String(length=64), nullable=False),
        sa.Column("accion", sa.String(length=32), nullable=False),
        sa.Column("campo", sa.String(length=64), nullable=True),
        sa.Column("clasificacion_minima", sa.String(length=24), nullable=False),
        sa.CheckConstraint(
            "clasificacion_minima IN ('publico', 'interno', 'personal', 'personal_sensible', 'menor')",
            name="permiso_clasificacion_valida",
        ),
        sa.PrimaryKeyConstraint("codigo"),
    )
    op.create_index("uq_permiso_tripleta", "permiso", ["recurso", "accion", "campo"], unique=True)
    op.create_table(
        "rol",
        sa.Column("codigo", sa.String(length=64), nullable=False),
        sa.Column("nombre", sa.String(length=128), nullable=False),
        sa.Column("descripcion", sa.String(length=512), nullable=False),
        sa.Column("del_sistema", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )
    op.create_table(
        "usuario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("correo", sa.String(length=320), nullable=False),
        sa.Column("clave_hash", sa.String(length=256), nullable=False),
        sa.Column("nombre_cifrado", sa.LargeBinary(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("version_permisos", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("anonimizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correo"),
    )
    op.create_table(
        "asignacion_rol",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("rol_codigo", sa.String(length=64), nullable=False),
        sa.Column("ambito_tipo", sa.String(length=16), nullable=False),
        sa.Column("ambito_id", sa.Uuid(), nullable=True),
        sa.Column(
            "vigente_desde", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("otorgado_por", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(ambito_tipo = 'global') = (ambito_id IS NULL)", name="asignacion_ambito_coherente"
        ),
        sa.CheckConstraint(
            "ambito_tipo IN ('global', 'colegio', 'sede', 'matricula')", name="asignacion_ambito_tipo_valido"
        ),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="asignacion_vigencia_coherente"
        ),
        sa.ForeignKeyConstraint(["otorgado_por"], ["usuario.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rol_codigo"], ["rol.codigo"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_asignacion_usuario_vigente", "asignacion_rol", ["usuario_id", "vigente_hasta"], unique=False
    )
    op.create_index(
        "uq_asignacion_rol_vigente",
        "asignacion_rol",
        [
            "usuario_id",
            "rol_codigo",
            "ambito_tipo",
            sa.literal_column("COALESCE(ambito_id, '00000000-0000-0000-0000-000000000000')"),
        ],
        unique=True,
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.create_table(
        "consentimiento_finalidad",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("finalidad", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("aceptado", sa.Boolean(), nullable=False),
        sa.Column(
            "vigente_desde", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "finalidad IN ('servicio', 'personalizacion', 'analitica')", name="finalidad_valida"
        ),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="finalidad_vigencia_coherente"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_consentimiento_finalidad_vigente",
        "consentimiento_finalidad",
        ["usuario_id", "finalidad"],
        unique=True,
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.create_table(
        "direccion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("etiqueta", sa.String(length=64), nullable=False),
        sa.Column("ciudad", sa.String(length=128), nullable=False),
        sa.Column("localidad", sa.String(length=128), nullable=True),
        sa.Column("linea_cifrada", sa.LargeBinary(), nullable=False),
        sa.Column("contacto_cifrado", sa.LargeBinary(), nullable=True),
        sa.Column("predeterminada", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archivada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_direccion_usuario", "direccion", ["usuario_id", "archivada_en"], unique=False)
    op.create_index(
        "uq_direccion_predeterminada",
        "direccion",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text("predeterminada AND archivada_en IS NULL"),
        sqlite_where=sa.text("predeterminada AND archivada_en IS NULL"),
    )
    op.create_table(
        "perfil_socioeconomico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("datos_cifrados", sa.LargeBinary(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id"),
    )
    op.create_table(
        "rol_permiso",
        sa.Column("rol_codigo", sa.String(length=64), nullable=False),
        sa.Column("permiso_codigo", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["permiso_codigo"], ["permiso.codigo"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rol_codigo"], ["rol.codigo"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rol_codigo", "permiso_codigo"),
    )
    op.create_table(
        "sede",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=256), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["colegio_id"], ["colegio.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sede_colegio", "sede", ["colegio_id"], unique=False)
    op.create_table(
        "solicitud_supresion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column(
            "suscriptores_confirmados",
            sa.JSON().with_variant(postgresql.ARRAY(sa.String(length=64)), "postgresql"),
            nullable=False,
        ),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(estado IN ('completada', 'fallida')) = (resuelto_en IS NOT NULL)",
            name="supresion_resolucion_coherente",
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'propagando', 'completada', 'fallida')", name="supresion_estado_valido"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "idempotency_key", name="uq_supresion_idempotente"),
    )
    op.create_index("ix_supresion_pendiente", "solicitud_supresion", ["estado"], unique=False)
    op.create_table(
        "matricula",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("estudiante_id", sa.Uuid(), nullable=False),
        sa.Column("sede_id", sa.Uuid(), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=False),
        sa.Column("grado", sa.String(length=32), nullable=False),
        sa.Column("anio_lectivo", sa.SmallInteger(), nullable=False),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cerrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(estado = 'activa') = (cerrado_en IS NULL)", name="matricula_cierre_coherente"),
        sa.CheckConstraint(
            "estado IN ('activa', 'retirada', 'graduada', 'archivada')", name="matricula_estado_valido"
        ),
        sa.CheckConstraint("anio_lectivo BETWEEN 2020 AND 2100", name="matricula_anio_plausible"),
        sa.ForeignKeyConstraint(["colegio_id"], ["colegio.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["estudiante_id"], ["estudiante.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sede_id"], ["sede.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("estudiante_id", "sede_id", "grado", "anio_lectivo", name="matricula_unica"),
    )
    op.create_index("ix_matricula_colegio", "matricula", ["colegio_id"], unique=False)
    op.create_index("ix_matricula_sede", "matricula", ["sede_id"], unique=False)
    op.create_table(
        "acudiente_matricula",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("matricula_id", sa.Uuid(), nullable=False),
        sa.Column("parentesco", sa.String(length=32), nullable=False),
        sa.Column("es_principal", sa.Boolean(), nullable=False),
        sa.Column(
            "vigente_desde", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="acudiente_vigencia_coherente"
        ),
        sa.ForeignKeyConstraint(["matricula_id"], ["matricula.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id", "matricula_id"),
    )
    op.create_index(
        "ix_acudiente_matricula_usuario", "acudiente_matricula", ["usuario_id", "vigente_hasta"], unique=False
    )
    op.create_index(
        "uq_matricula_principal",
        "acudiente_matricula",
        ["matricula_id"],
        unique=True,
        postgresql_where=sa.text("es_principal AND vigente_hasta IS NULL"),
        sqlite_where=sa.text("es_principal AND vigente_hasta IS NULL"),
    )
    op.create_table(
        "consentimiento",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("regimen", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("matricula_id", sa.Uuid(), nullable=True),
        sa.Column("aceptado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(regimen = 'registro_menor') = (matricula_id IS NOT NULL)", name="consentimiento_menor_coherente"
        ),
        sa.CheckConstraint(
            "regimen IN ('registro_titular', 'registro_menor')", name="consentimiento_regimen_valido"
        ),
        sa.CheckConstraint(
            "revocado_en IS NULL OR revocado_en >= aceptado_en", name="consentimiento_revocacion_coherente"
        ),
        sa.ForeignKeyConstraint(["matricula_id"], ["matricula.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consentimiento_matricula", "consentimiento", ["matricula_id"], unique=False)
    op.create_index("ix_consentimiento_usuario", "consentimiento", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_consentimiento_usuario", table_name="consentimiento")
    op.drop_index("ix_consentimiento_matricula", table_name="consentimiento")
    op.drop_table("consentimiento")
    op.drop_index(
        "uq_matricula_principal",
        table_name="acudiente_matricula",
        postgresql_where=sa.text("es_principal AND vigente_hasta IS NULL"),
        sqlite_where=sa.text("es_principal AND vigente_hasta IS NULL"),
    )
    op.drop_index("ix_acudiente_matricula_usuario", table_name="acudiente_matricula")
    op.drop_table("acudiente_matricula")
    op.drop_index("ix_matricula_sede", table_name="matricula")
    op.drop_index("ix_matricula_colegio", table_name="matricula")
    op.drop_table("matricula")
    op.drop_index("ix_supresion_pendiente", table_name="solicitud_supresion")
    op.drop_table("solicitud_supresion")
    op.drop_index("ix_sede_colegio", table_name="sede")
    op.drop_table("sede")
    op.drop_table("rol_permiso")
    op.drop_table("perfil_socioeconomico")
    op.drop_index(
        "uq_direccion_predeterminada",
        table_name="direccion",
        postgresql_where=sa.text("predeterminada AND archivada_en IS NULL"),
        sqlite_where=sa.text("predeterminada AND archivada_en IS NULL"),
    )
    op.drop_index("ix_direccion_usuario", table_name="direccion")
    op.drop_table("direccion")
    op.drop_index(
        "uq_consentimiento_finalidad_vigente",
        table_name="consentimiento_finalidad",
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.drop_table("consentimiento_finalidad")
    op.drop_index(
        "uq_asignacion_rol_vigente",
        table_name="asignacion_rol",
        postgresql_where=sa.text("vigente_hasta IS NULL"),
        sqlite_where=sa.text("vigente_hasta IS NULL"),
    )
    op.drop_index("ix_asignacion_usuario_vigente", table_name="asignacion_rol")
    op.drop_table("asignacion_rol")
    op.drop_table("usuario")
    op.drop_table("rol")
    op.drop_index("uq_permiso_tripleta", table_name="permiso")
    op.drop_table("permiso")
    op.drop_index(
        "uq_estudiante_documento",
        table_name="estudiante",
        postgresql_where=sa.text("documento_hash IS NOT NULL"),
        sqlite_where=sa.text("documento_hash IS NOT NULL"),
    )
    op.drop_table("estudiante")
    op.drop_table("colegio")
    op.drop_index(
        "ix_bandeja_pendiente",
        table_name="bandeja_salida",
        postgresql_where=sa.text("publicado_en IS NULL"),
        sqlite_where=sa.text("publicado_en IS NULL"),
    )
    op.drop_table("bandeja_salida")
