from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

FINALIDADES = ("servicio", "personalizacion", "analitica")
REGIMENES = ("registro_titular", "registro_menor")
ESTADOS_SUPRESION = ("pendiente", "propagando", "completada", "fallida")

_LISTA_FINALIDADES = ", ".join(f"'{f}'" for f in FINALIDADES)
_LISTA_REGIMENES = ", ".join(f"'{r}'" for r in REGIMENES)
_LISTA_ESTADOS = ", ".join(f"'{e}'" for e in ESTADOS_SUPRESION)


class PerfilSocioeconomico(Base):
    __tablename__ = "perfil_socioeconomico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    datos_cifrados: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Consentimiento(Base):
    __tablename__ = "consentimiento"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    regimen: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("matricula.id", ondelete="RESTRICT"), nullable=True
    )
    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"regimen IN ({_LISTA_REGIMENES})", name="consentimiento_regimen_valido"),
        CheckConstraint(
            "(regimen = 'registro_menor') = (matricula_id IS NOT NULL)", name="consentimiento_menor_coherente"
        ),
        CheckConstraint(
            "revocado_en IS NULL OR revocado_en >= aceptado_en", name="consentimiento_revocacion_coherente"
        ),
        Index("ix_consentimiento_usuario", "usuario_id"),
        Index("ix_consentimiento_matricula", "matricula_id"),
    )

    @property
    def vigente(self) -> bool:
        return self.revocado_en is None


class ConsentimientoFinalidad(Base):
    __tablename__ = "consentimiento_finalidad"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    finalidad: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    aceptado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"finalidad IN ({_LISTA_FINALIDADES})", name="finalidad_valida"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="finalidad_vigencia_coherente"
        ),
        Index(
            "uq_consentimiento_finalidad_vigente",
            "usuario_id",
            "finalidad",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
            sqlite_where=text("vigente_hasta IS NULL"),
        ),
    )

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None


class SolicitudSupresion(Base):
    __tablename__ = "solicitud_supresion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    suscriptores_confirmados: Mapped[list[str]] = mapped_column(
        JSON().with_variant(ARRAY(String(64)), "postgresql"), nullable=False, default=list
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_LISTA_ESTADOS})", name="supresion_estado_valido"),
        CheckConstraint(
            "(estado IN ('completada', 'fallida')) = (resuelto_en IS NOT NULL)",
            name="supresion_resolucion_coherente",
        ),
        UniqueConstraint("usuario_id", "idempotency_key", name="uq_supresion_idempotente"),
        Index("ix_supresion_pendiente", "estado"),
    )

    def confirmar(self, servicio: str, suscriptores_requeridos: frozenset[str]) -> bool:
        if servicio not in self.suscriptores_confirmados:
            self.suscriptores_confirmados = [*self.suscriptores_confirmados, servicio]
        return suscriptores_requeridos.issubset(set(self.suscriptores_confirmados))
