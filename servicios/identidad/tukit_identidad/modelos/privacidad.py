"""Consentimiento, perfil socioeconomico y supresion.

Estas cuatro tablas son la razon por la que Identidad es una frontera de
cumplimiento y no un servicio mas. Cada una corrige un defecto concreto que el
Anexo M documento sobre el modelo anterior, y los cuatro defectos tienen la
misma forma: la politica existia en el documento y el esquema no la soportaba.
"""

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
    """La encuesta P1 a P9, en un contenedor cifrado.

    Los nueve atributos NO son columnas: viven dentro de `datos_cifrados` y se
    descifran en la aplicacion. Uno de ellos, el numero de hijos escolarizados,
    esta clasificado como dato de menor.

    Se queda en Identidad por frontera de cumplimiento, y eso deja abierto un
    problema que el esquema no puede cerrar solo: sus derivados
    (`kit.perfil` y `kit.pesos_usados`) viven en claro en la base de
    Inteligencia. Cifrar el origen y dejar el derivado en claro no protege
    nada. Se resuelve en el porte de Inteligencia, no aqui.
    """

    __tablename__ = "perfil_socioeconomico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    datos_cifrados: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Sin esta columna la retencion de 24 meses que fija el Anexo M es
    # inejecutable: no habria desde donde contarlos. Mismo caso que
    # `matricula.cerrado_en`.
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Consentimiento(Base):
    """Aceptacion de un texto legal, con regimen y version.

    Fusiona las dos tablas anteriores bajo un discriminador, y agrega la
    columna que corrige el defecto mas concreto del modelo previo:
    `consentimientos_menor_registro` registraba que un acudiente autorizo el
    tratamiento del dato de UN hijo pero no decia de cual. Con dos hijos, una
    sola fila cubria a ambos de forma indistinguible, lo que hace imposible
    revocar el consentimiento de uno solo y hace imposible responderle a un
    regulador que autorizo exactamente el titular.
    """

    __tablename__ = "consentimiento"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    regimen: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    # De cual menor se autoriza el tratamiento. Nulo solo para el regimen del
    # titular, y el CHECK lo impone.
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("matricula.id", ondelete="RESTRICT"), nullable=True
    )
    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Una revocatoria que sobreescribe la fila borra la evidencia de lo que se
    # revoco, y con eso no sirve ni al titular ni a la prueba de cumplimiento.
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
    """Decision del titular sobre una finalidad concreta, versionada y con historial.

    El esquema anterior tenia clave primaria compuesta `(usuario_id, finalidad)`,
    asi que un `PUT` sobreescribia la fila: no habia version ni historico. Se
    corrige con clave sustituta mas indice unico parcial sobre la fila vigente,
    el mismo patron que usa `asignacion_rol` para el mismo problema.

    Arreglar la forma NO arregla el hallazgo de fondo: esta tabla no se
    consulta desde ningun punto del sistema antes de tratar un dato, asi que la
    revocacion es hoy un interruptor sin efecto. Un consentimiento que no se
    consulta no es un consentimiento, es un formulario. El esquema habilita el
    control; imponerlo es trabajo del codigo que trata el dato.
    """

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
    """Ejercicio del derecho de supresion, con confirmacion de todos los servicios.

    El estado `propagando` y la columna `suscriptores_confirmados` existen para
    volver verdadero el estado `completada`. El worker anterior marcaba la
    solicitud como completada inmediatamente despues de anonimizar la fila
    local, sin esperar confirmacion de nadie, y la publicacion del evento hacia
    los demas servicios se tragaba el fallo sin reintento.

    El sistema le respondia al titular que su dato fue suprimido cuando, en el
    mejor de los casos, lo habia sido en una de las cinco bases.
    """

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
        # `completada` y `fallida` son terminales y exigen fecha de resolucion:
        # es lo que impide volver a marcar completada una solicitud que nadie
        # confirmo.
        CheckConstraint(
            "(estado IN ('completada', 'fallida')) = (resuelto_en IS NOT NULL)",
            name="supresion_resolucion_coherente",
        ),
        UniqueConstraint("usuario_id", "idempotency_key", name="uq_supresion_idempotente"),
        Index("ix_supresion_pendiente", "estado"),
    )

    def confirmar(self, servicio: str, suscriptores_requeridos: frozenset[str]) -> bool:
        """Registra la confirmacion de un servicio. Devuelve si ya estan todas.

        Vive en el modelo y no en el worker porque la regla que hay que
        sostener es precisamente que `completada` signifique lo que dice, y
        dejarla en el llamador es como el worker anterior termino marcando
        completada una supresion que solo habia ocurrido localmente.
        """
        if servicio not in self.suscriptores_confirmados:
            self.suscriptores_confirmados = [*self.suscriptores_confirmados, servicio]
        return suscriptores_requeridos.issubset(set(self.suscriptores_confirmados))
