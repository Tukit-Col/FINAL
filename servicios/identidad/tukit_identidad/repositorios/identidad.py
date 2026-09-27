"""El SQL de autorizacion: resuelve `Ambito` contra `asignacion_rol` y sus vecinas.

Todo lo que aqui vive salio, verbatim en la logica, de `autorizacion.py`: la
cadena de contencion, los roles vigentes, `puede()` y la visibilidad por campo
o por matricula. Lo unico que cambio de forma es la superficie: eran funciones
sueltas que recibian `db` en cada llamada; aqui son metodos de `RepoIdentidad`,
atado a una conexion, igual que `RepoCasos`/`RepoPedidos` en los otros
servicios. `Ambito` es dato puro y vive en `dominio/autorizacion.py`; aqui solo
el SQL que lo resuelve (ADR 0013, ADR 0019).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from ..dominio.autorizacion import Ambito
from ..modelos import (
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


class RepoIdentidad:
    """Resuelve permisos con ambito, atado a una conexion de una unidad de
    trabajo. Se construye dentro del `async with motor.sesion()` de quien la
    use, con la conexion ya abierta; no abre ni cierra la sesion."""

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def _cadena_de_contencion(self, ambito: Ambito) -> list[Ambito]:
        """Ambitos que CONTIENEN al pedido, del mas amplio al mas estrecho.

        Un rol otorgado sobre un colegio alcanza sus sedes y las matriculas de
        esas sedes. Al reves no: ser acudiente de una matricula no da autoridad
        sobre la sede. Resolver la cadena es lo que hace que la jerarquia
        funcione sin duplicar asignaciones en cada nivel.
        """
        cadena: list[Ambito] = [Ambito.global_()]

        if ambito.tipo is AmbitoTipo.GLOBAL:
            return cadena

        if ambito.tipo is AmbitoTipo.COLEGIO:
            cadena.append(ambito)
            return cadena

        if ambito.tipo is AmbitoTipo.SEDE:
            colegio_id = await self.conexion.scalar(select(Sede.colegio_id).where(Sede.id == ambito.id))
            if colegio_id:
                cadena.append(Ambito.colegio(colegio_id))
            cadena.append(ambito)
            return cadena

        # MATRICULA: sube hasta el colegio pasando por la sede.
        fila = (
            await self.conexion.execute(
                select(Matricula.sede_id, Matricula.colegio_id).where(Matricula.id == ambito.id)
            )
        ).first()
        if fila:
            cadena.append(Ambito.colegio(fila.colegio_id))
            cadena.append(Ambito.sede(fila.sede_id))
        cadena.append(ambito)
        return cadena

    async def roles_vigentes(self, usuario_id: uuid.UUID, ambito: Ambito) -> set[str]:
        """Roles que el usuario tiene vigentes sobre `ambito` o sobre algo que lo contenga."""
        cadena = await self._cadena_de_contencion(ambito)
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
        return set((await self.conexion.scalars(consulta)).all())

    async def puede(self, usuario_id: uuid.UUID, permiso: str, ambito: Ambito) -> bool:
        """¿Puede este usuario ejercer `permiso` sobre `ambito`?

        Falla CERRADA: sin asignacion vigente que alcance el ambito, es
        `False`. No hay rama que conceda por ausencia de contexto.
        """
        roles = await self.roles_vigentes(usuario_id, ambito)
        if not roles:
            return False

        existe = await self.conexion.scalar(
            select(RolPermiso.permiso_codigo)
            .where(RolPermiso.rol_codigo.in_(roles), RolPermiso.permiso_codigo == permiso)
            .limit(1)
        )
        return existe is not None

    async def campos_visibles(
        self,
        usuario_id: uuid.UUID,
        recurso: str,
        ambito: Ambito,
        clasificacion_por_campo: dict[str, Clasificacion],
    ) -> set[str]:
        """Campos de `recurso` que este usuario puede LEER en este ambito.

        Dos ejes, no uno. El permiso dice quien ve que; la clasificacion dice
        que tan sensible es. Un permiso `estudiante:leer` con
        `clasificacion_minima` de `interno` NO alcanza un campo clasificado
        `menor`, aunque el permiso nombre el recurso.
        """
        roles = await self.roles_vigentes(usuario_id, ambito)
        if not roles:
            return set()

        filas = (
            await self.conexion.execute(
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

    async def matriculas_visibles(self, usuario_id: uuid.UUID) -> set[uuid.UUID]:
        """Matriculas que este usuario alcanza, por vinculo o por rol con ambito.

        Las politicas son ASIMETRICAS a proposito: para LEER basta que el
        recurso toque alguna matricula visible; para ESCRIBIR tienen que estar
        TODAS contenidas.
        """
        ahora = datetime.now(UTC)

        directas = set(
            (
                await self.conexion.scalars(
                    select(AcudienteMatricula.matricula_id).where(
                        AcudienteMatricula.usuario_id == usuario_id,
                        AcudienteMatricula.vigente_desde <= ahora,
                        or_(
                            AcudienteMatricula.vigente_hasta.is_(None),
                            AcudienteMatricula.vigente_hasta > ahora,
                        ),
                    )
                )
            ).all()
        )

        asignaciones = (
            await self.conexion.execute(
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
            por_rol |= set((await self.conexion.scalars(select(Matricula.id).where(or_(*condiciones)))).all())

        return directas | por_rol
