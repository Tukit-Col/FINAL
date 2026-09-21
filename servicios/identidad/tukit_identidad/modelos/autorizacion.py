"""Modelo de autorizacion: roles con ambito en vez de una cadena plana.

Sustituye `usuarios.rol String(50)`, donde `require_rol` hacia literalmente
`if user.get("rol") not in roles`. Con eso, el administrador del colegio A y el
del colegio B pasaban exactamente el mismo control, y la unica defensa era que
cada endpoint se acordara de comparar el colegio del token contra el del
recurso. La auditoria conto 152 endpoints, 22 con hueco de ambito y 46 que
comparan bien pero con codigo escrito a mano y distinto en cada servicio.

Ver ADR 0013.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import AmbitoTipo, Base, Clasificacion

_NIVELES = ", ".join(f"'{c.value}'" for c in Clasificacion)
_AMBITOS = ", ".join(f"'{a.value}'" for a in AmbitoTipo)


class Rol(Base):
    """Un rol es una fila, no un valor de un enumerado.

    Esa es la diferencia que hace que agregar un rol deje de ser una migracion
    y un despliegue. Cuando entre el primer colegio que quiera un coordinador
    de primaria distinto de la rectoria, se configura.
    """

    __tablename__ = "rol"

    codigo: Mapped[str] = mapped_column(String(64), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    del_sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permiso(Base):
    """Un permiso es `recurso:accion` y opcionalmente `:campo`.

    `campo` es lo que da seguridad a nivel de campo con el mismo mecanismo que
    da seguridad a nivel de fila: `estudiante:leer` y `estudiante:leer:nombre`
    son permisos distintos.
    """

    __tablename__ = "permiso"

    codigo: Mapped[str] = mapped_column(String(128), primary_key=True)
    recurso: Mapped[str] = mapped_column(String(64), nullable=False)
    accion: Mapped[str] = mapped_column(String(32), nullable=False)
    # Nulo significa "todo el recurso", no "ningun campo".
    campo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clasificacion_minima: Mapped[str] = mapped_column(
        String(24), nullable=False, default=Clasificacion.INTERNO.value
    )

    __table_args__ = (
        CheckConstraint(f"clasificacion_minima IN ({_NIVELES})", name="permiso_clasificacion_valida"),
        Index("uq_permiso_tripleta", "recurso", "accion", "campo", unique=True),
    )


class RolPermiso(Base):
    __tablename__ = "rol_permiso"

    rol_codigo: Mapped[str] = mapped_column(ForeignKey("rol.codigo", ondelete="CASCADE"), primary_key=True)
    permiso_codigo: Mapped[str] = mapped_column(
        ForeignKey("permiso.codigo", ondelete="CASCADE"), primary_key=True
    )


class AsignacionRol(Base):
    """`(usuario, rol, ambito)`, con historial.

    Absorbe `pertenencias_institucion` de MS-Instituciones, que ya era una
    asignacion de rol con ambito funcionando: la fila
    `(usuario, institucion, rol)` es exactamente
    `(usuario, rol, ambito_tipo='colegio', ambito_id)`. Lo que se corrige de
    ella es que su `UniqueConstraint(usuario_id, institucion_id)` obliga a
    BORRAR la fila para revocar, y con eso se pierde la evidencia de quien
    tuvo acceso a que y cuando. Aqui se revoca poniendo `vigente_hasta`.
    """

    __tablename__ = "asignacion_rol"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    rol_codigo: Mapped[str] = mapped_column(ForeignKey("rol.codigo", ondelete="RESTRICT"), nullable=False)
    ambito_tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    # Nulo SOLO para el ambito global; lo impone `asignacion_ambito_coherente`.
    ambito_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    otorgado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(f"ambito_tipo IN ({_AMBITOS})", name="asignacion_ambito_tipo_valido"),
        CheckConstraint("(ambito_tipo = 'global') = (ambito_id IS NULL)", name="asignacion_ambito_coherente"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="asignacion_vigencia_coherente"
        ),
        # Indice unico PARCIAL: impide dos asignaciones vigentes identicas sin
        # impedir el historial. Un indice unico total obligaria a borrar para
        # reasignar, que es el defecto de `pertenencias_institucion`.
        Index(
            "uq_asignacion_rol_vigente",
            "usuario_id",
            "rol_codigo",
            "ambito_tipo",
            text("COALESCE(ambito_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
            sqlite_where=text("vigente_hasta IS NULL"),
        ),
        Index("ix_asignacion_usuario_vigente", "usuario_id", "vigente_hasta"),
    )

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None
