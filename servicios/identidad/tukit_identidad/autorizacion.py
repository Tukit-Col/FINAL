"""Resolucion de permisos con ambito.

Reemplaza `require_rol(*roles)`, que hacia `if user.get("rol") not in roles`.
Ese control respondia "que es este usuario" cuando la pregunta correcta es
"que puede hacer este usuario SOBRE ESTE recurso". El administrador del
colegio A y el del colegio B lo pasaban igual, y lo unico que los separaba era
que cada endpoint se acordara de comparar el colegio del token contra el del
recurso, escrito a mano y distinto en cada servicio.

La pregunta que responde este modulo es `puede(usuario, permiso, ambito)`.

Ver ADR 0013.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .modelos import (
    ORDEN_CLASIFICACION,
    AcudienteMatricula,
    AmbitoTipo,
    AsignacionRol,
    Clasificacion,
    Matricula,
    Permiso,
    RolPermiso,
    Sede,
)


@dataclass(frozen=True, slots=True)
class Ambito:
    """Sobre que se pregunta. `GLOBAL` no lleva identificador."""

    tipo: AmbitoTipo
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        # Misma regla que el CHECK `asignacion_ambito_coherente`. Se valida
        # tambien aqui para que un ambito mal armado falle al construirse y no
        # al comparar, donde el error seria un permiso denegado sin explicacion.
        if (self.tipo is AmbitoTipo.GLOBAL) != (self.id is None):
            raise ValueError(
                f"Ambito incoherente: tipo={self.tipo} con id={self.id}. "
                "El ambito global no lleva identificador, y los demas si."
            )

    @classmethod
    def global_(cls) -> Ambito:
        return cls(AmbitoTipo.GLOBAL)

    @classmethod
    def colegio(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.COLEGIO, id)

    @classmethod
    def sede(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.SEDE, id)

    @classmethod
    def matricula(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.MATRICULA, id)


async def _cadena_de_contencion(db: AsyncSession, ambito: Ambito) -> list[Ambito]:
    """Ambitos que CONTIENEN al pedido, del mas amplio al mas estrecho.

    Un rol otorgado sobre un colegio alcanza sus sedes y las matriculas de esas
    sedes. Al reves no: ser acudiente de una matricula no da autoridad sobre la
    sede. Resolver la cadena es lo que hace que la jerarquia funcione sin
    duplicar asignaciones en cada nivel.
    """
    cadena: list[Ambito] = [Ambito.global_()]

    if ambito.tipo is AmbitoTipo.GLOBAL:
        return cadena

    if ambito.tipo is AmbitoTipo.COLEGIO:
        cadena.append(ambito)
        return cadena

    if ambito.tipo is AmbitoTipo.SEDE:
        colegio_id = await db.scalar(select(Sede.colegio_id).where(Sede.id == ambito.id))
        if colegio_id:
            cadena.append(Ambito.colegio(colegio_id))
        cadena.append(ambito)
        return cadena

    # MATRICULA: sube hasta el colegio pasando por la sede.
    fila = (
        await db.execute(select(Matricula.sede_id, Matricula.colegio_id).where(Matricula.id == ambito.id))
    ).first()
    if fila:
        cadena.append(Ambito.colegio(fila.colegio_id))
        cadena.append(Ambito.sede(fila.sede_id))
    cadena.append(ambito)
    return cadena


async def roles_vigentes(db: AsyncSession, usuario_id: uuid.UUID, ambito: Ambito) -> set[str]:
    """Roles que el usuario tiene vigentes sobre `ambito` o sobre algo que lo contenga."""
    cadena = await _cadena_de_contencion(db, ambito)
    ahora = datetime.now(UTC)

    condiciones = [
        (AsignacionRol.ambito_tipo == a.tipo.value)
        & (AsignacionRol.ambito_id.is_(None) if a.id is None else AsignacionRol.ambito_id == a.id)
        for a in cadena
    ]

    consulta = select(AsignacionRol.rol_codigo).where(
        AsignacionRol.usuario_id == usuario_id,
        AsignacionRol.vigente_desde <= ahora,
        or_(AsignacionRol.vigente_hasta.is_(None), AsignacionRol.vigente_hasta > ahora),
        or_(*condiciones),
    )
    return set((await db.scalars(consulta)).all())


async def puede(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    permiso: str,
    ambito: Ambito,
) -> bool:
    """¿Puede este usuario ejercer `permiso` sobre `ambito`?

    Falla CERRADA: sin asignacion vigente que alcance el ambito, es `False`.
    No hay rama que conceda por ausencia de contexto.

    Esa aclaracion no sobra. Las politicas de seguridad a nivel de fila del
    sistema anterior empezaban su condicion con
    `current_setting('app.current_user_id', true) IS NULL`, de modo que toda
    conexion sin contexto veia la tabla completa: el control fallaba ABIERTO y
    su caso mas probable de fallo, olvidar poner el contexto, era justo el que
    concedia todo.
    """
    roles = await roles_vigentes(db, usuario_id, ambito)
    if not roles:
        return False

    existe = await db.scalar(
        select(RolPermiso.permiso_codigo)
        .where(RolPermiso.rol_codigo.in_(roles), RolPermiso.permiso_codigo == permiso)
        .limit(1)
    )
    return existe is not None


async def campos_visibles(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    recurso: str,
    ambito: Ambito,
    clasificacion_por_campo: dict[str, Clasificacion],
) -> set[str]:
    """Campos de `recurso` que este usuario puede LEER en este ambito.

    Seguridad a nivel de campo con el mismo mecanismo que la de fila. Se
    resuelve en un solo lugar y se aplica al serializar, porque la alternativa
    (que cada endpoint recuerde excluir el campo sensible) ya se probo: la
    auditoria encontro 22 endpoints con hueco de ambito por exactamente esa
    razon.

    Dos ejes, no uno. El permiso dice quien ve que; la clasificacion dice que
    tan sensible es. Un permiso `estudiante:leer` con `clasificacion_minima`
    de `interno` NO alcanza un campo clasificado `menor`, aunque el permiso
    nombre el recurso. Derivar los permisos automaticamente de la
    clasificacion, como afirmaba el rediseno, colapsa los dos ejes en uno.
    """
    roles = await roles_vigentes(db, usuario_id, ambito)
    if not roles:
        return set()

    filas = (
        await db.execute(
            select(Permiso.campo, Permiso.clasificacion_minima)
            .join(RolPermiso, RolPermiso.permiso_codigo == Permiso.codigo)
            .where(RolPermiso.rol_codigo.in_(roles), Permiso.recurso == recurso, Permiso.accion == "leer")
        )
    ).all()
    if not filas:
        return set()

    # Un permiso sin `campo` cubre el recurso entero hasta su clasificacion.
    techo_general = -1
    techo_por_campo: dict[str, int] = {}
    for campo, minima in filas:
        nivel = ORDEN_CLASIFICACION[Clasificacion(minima)]
        if campo is None:
            techo_general = max(techo_general, nivel)
        else:
            techo_por_campo[campo] = max(techo_por_campo.get(campo, -1), nivel)

    return {
        campo
        for campo, clasificacion in clasificacion_por_campo.items()
        if max(techo_general, techo_por_campo.get(campo, -1)) >= ORDEN_CLASIFICACION[clasificacion]
    }


async def matriculas_visibles(db: AsyncSession, usuario_id: uuid.UUID) -> set[uuid.UUID]:
    """Matriculas que este usuario alcanza, por vinculo o por rol con ambito.

    Es el conjunto contra el que se escriben las politicas de fila de los otros
    servicios, y por eso vive aqui y no replicado en cada uno.

    Las politicas son ASIMETRICAS a proposito: para LEER basta que el recurso
    toque alguna matricula visible; para ESCRIBIR tienen que estar TODAS
    contenidas. Un pedido con dos hermanos, uno visible y otro no, se puede
    consultar pero no modificar.
    """
    ahora = datetime.now(UTC)

    directas = set(
        (
            await db.scalars(
                select(AcudienteMatricula.matricula_id).where(
                    AcudienteMatricula.usuario_id == usuario_id,
                    AcudienteMatricula.vigente_desde <= ahora,
                    or_(AcudienteMatricula.vigente_hasta.is_(None), AcudienteMatricula.vigente_hasta > ahora),
                )
            )
        ).all()
    )

    asignaciones = (
        await db.execute(
            select(AsignacionRol.ambito_tipo, AsignacionRol.ambito_id).where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.vigente_desde <= ahora,
                or_(AsignacionRol.vigente_hasta.is_(None), AsignacionRol.vigente_hasta > ahora),
            )
        )
    ).all()

    colegios = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.COLEGIO.value}
    sedes = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.SEDE.value}
    por_rol = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.MATRICULA.value}

    if colegios or sedes:
        condiciones = []
        if colegios:
            condiciones.append(Matricula.colegio_id.in_(colegios))
        if sedes:
            condiciones.append(Matricula.sede_id.in_(sedes))
        por_rol |= set((await db.scalars(select(Matricula.id).where(or_(*condiciones)))).all())

    return directas | por_rol
