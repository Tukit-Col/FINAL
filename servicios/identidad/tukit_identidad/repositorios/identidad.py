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

from sqlalchemy import and_, func, insert, or_, select, update

from ..dominio.autorizacion import Ambito
from ..modelos import (
    ORDEN_CLASIFICACION,
    AcudienteMatricula,
    AmbitoTipo,
    AsignacionRol,
    Base,
    Clasificacion,
    Matricula,
    Permiso,
    RolPermiso,
    Sede,
)

# Las tablas del SQL de handler se resuelven una vez, como en api.py. Los
# modelos ORM (AsignacionRol, Matricula, ...) los usa el SQL de autorizacion;
# el de handler va contra la tabla Core, que es la forma que ya tenia api.py.
COLEGIO = Base.metadata.tables["colegio"]
SEDE_T = Base.metadata.tables["sede"]
USUARIO = Base.metadata.tables["usuario"]
ASIGNACION_ROL = Base.metadata.tables["asignacion_rol"]
DIRECCION = Base.metadata.tables["direccion"]
ESTUDIANTE = Base.metadata.tables["estudiante"]
MATRICULA = Base.metadata.tables["matricula"]
ACUDIENTE_MATRICULA = Base.metadata.tables["acudiente_matricula"]
CONSENTIMIENTO = Base.metadata.tables["consentimiento"]


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

    # ------------------------------------------------------------------
    # SQL de handler: colegios, contacto, sesion y libreta de direcciones.
    # Salio verbatim de api.py; lo unico que cambia es que va contra
    # self.conexion en vez de una `engine.begin()` abierta en cada ruta.
    # ------------------------------------------------------------------

    async def listar_colegios(self, busqueda: str | None) -> list[Any]:
        consulta = (
            select(
                COLEGIO.c.id,
                COLEGIO.c.nombre,
                COLEGIO.c.logo_url,
                func.count(SEDE_T.c.id).label("sedes"),
            )
            .select_from(
                COLEGIO.outerjoin(SEDE_T, and_(SEDE_T.c.colegio_id == COLEGIO.c.id, SEDE_T.c.activa.is_(True)))
            )
            .where(COLEGIO.c.activo.is_(True))
            .group_by(COLEGIO.c.id, COLEGIO.c.nombre, COLEGIO.c.logo_url)
            .order_by(COLEGIO.c.nombre)
        )
        if busqueda:
            consulta = consulta.where(func.lower(COLEGIO.c.nombre).like(f"%{busqueda.lower()}%"))
        return list(await self.conexion.execute(consulta))

    async def ver_colegio(self, colegio_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(COLEGIO).where(COLEGIO.c.id == colegio_id))).one_or_none()

    async def sedes_de(self, colegio_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(SEDE_T).where(SEDE_T.c.colegio_id == colegio_id, SEDE_T.c.activa.is_(True))
            )
        )

    async def existe_colegio(self, colegio_id: uuid.UUID) -> uuid.UUID | None:
        return await self.conexion.scalar(select(COLEGIO.c.id).where(COLEGIO.c.id == colegio_id))

    async def editar_colegio(self, colegio_id: uuid.UUID, valores: dict[str, Any]) -> None:
        if valores:
            await self.conexion.execute(update(COLEGIO).where(COLEGIO.c.id == colegio_id).values(**valores))

    async def usuario_por_correo(self, correo: str) -> Any:
        return (await self.conexion.execute(select(USUARIO).where(USUARIO.c.correo == correo))).one_or_none()

    async def registrar_contacto(self, correo: str) -> tuple[uuid.UUID, bool]:
        existente = await self.conexion.scalar(select(USUARIO.c.id).where(USUARIO.c.correo == correo))
        if existente is not None:
            return existente, False
        nuevo = uuid.uuid4()
        # Centinela y no cadena vacia: una cadena vacia se parece demasiado a un
        # hash y algun verificador la podria comparar. Esto no valida contra nada.
        await self.conexion.execute(insert(USUARIO).values(id=nuevo, correo=correo, clave_hash="sin-credencial"))
        return nuevo, True

    async def contacto_de(self, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(USUARIO.c.correo, USUARIO.c.activo).where(USUARIO.c.id == usuario_id)
            )
        ).one_or_none()

    async def armar_sesion(self, fila_usuario: Any) -> dict[str, Any]:
        """La Sesion publica: quien es y que roles vigentes tiene. Los roles
        salen de `asignacion_rol` (vigentes, sin caducar); el nombre va
        descifrado con el cifrador del entorno."""
        ahora = datetime.now(UTC)
        filas = await self.conexion.execute(
            select(
                ASIGNACION_ROL.c.rol_codigo, ASIGNACION_ROL.c.ambito_tipo, ASIGNACION_ROL.c.ambito_id
            ).where(
                ASIGNACION_ROL.c.usuario_id == fila_usuario.id,
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
        )
        roles = [
            {
                "rol": f.rol_codigo,
                "ambito": {"tipo": f.ambito_tipo, "id": str(f.ambito_id) if f.ambito_id is not None else None},
            }
            for f in filas
        ]
        nombre = fila_usuario.correo
        if fila_usuario.nombre_cifrado is not None:
            from tukit_comun.cifrado import cifrador_desde_entorno

            nombre = cifrador_desde_entorno().descifrar(fila_usuario.nombre_cifrado).decode(
                "utf-8", errors="replace"
            )
        return {
            "usuario_id": str(fila_usuario.id),
            "correo": fila_usuario.correo,
            "nombre": nombre,
            "roles": roles,
            "version_permisos": int(fila_usuario.version_permisos),
        }

    async def usuario_del_token(self, usuario_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))).one_or_none()

    async def direcciones_de(self, usuario_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(DIRECCION)
                .where(DIRECCION.c.usuario_id == usuario_id, DIRECCION.c.archivada_en.is_(None))
                .order_by(DIRECCION.c.predeterminada.desc(), DIRECCION.c.creado_en)
            )
        )

    async def limpiar_predeterminada(self, usuario_id: uuid.UUID) -> None:
        """Baja la marca de la anterior predeterminada, para que el indice unico
        parcial no choque cuando llega una nueva."""
        await self.conexion.execute(
            update(DIRECCION)
            .where(
                DIRECCION.c.usuario_id == usuario_id,
                DIRECCION.c.predeterminada.is_(True),
                DIRECCION.c.archivada_en.is_(None),
            )
            .values(predeterminada=False)
        )

    async def crear_direccion(self, **valores: Any) -> Any:
        nueva = uuid.uuid4()
        await self.conexion.execute(insert(DIRECCION).values(id=nueva, **valores))
        return (await self.conexion.execute(select(DIRECCION).where(DIRECCION.c.id == nueva))).one()

    async def obtener_direccion(self, direccion_id: uuid.UUID, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(DIRECCION).where(
                    DIRECCION.c.id == direccion_id,
                    DIRECCION.c.usuario_id == usuario_id,
                    DIRECCION.c.archivada_en.is_(None),
                )
            )
        ).one_or_none()

    async def editar_direccion(self, direccion_id: uuid.UUID, **valores: Any) -> Any:
        await self.conexion.execute(update(DIRECCION).where(DIRECCION.c.id == direccion_id).values(**valores))
        return (await self.conexion.execute(select(DIRECCION).where(DIRECCION.c.id == direccion_id))).one()

    async def archivar_direccion(self, direccion_id: uuid.UUID, usuario_id: uuid.UUID) -> int:
        resultado = await self.conexion.execute(
            update(DIRECCION)
            .where(
                DIRECCION.c.id == direccion_id,
                DIRECCION.c.usuario_id == usuario_id,
                DIRECCION.c.archivada_en.is_(None),
            )
            .values(archivada_en=datetime.now(UTC), predeterminada=False)
        )
        return resultado.rowcount

    async def crear_o_promover_cuenta(
        self, *, correo: str, clave: str, nombre: str, celular: str | None
    ) -> tuple[Any, Any]:
        """Aplica la decision del dominio: crea, promueve al invitado, o
        devuelve CONFLICTO sin tocar nada (el router lo traduce a 409)."""
        from tukit_comun.cifrado import cifrador_desde_entorno

        from ..dominio.cuenta import Decision, decide_creacion
        from ..dominio.sesiones import hashear_clave

        fila = await self.usuario_por_correo(correo)
        decision = decide_creacion(fila.clave_hash if fila is not None else None)
        if decision is Decision.CONFLICTO:
            return fila, decision

        nombre_cifrado = cifrador_desde_entorno().cifrar(nombre.encode("utf-8"))
        clave_hash = hashear_clave(clave)

        if decision is Decision.PROMOVER:
            await self.conexion.execute(
                update(USUARIO)
                .where(USUARIO.c.id == fila.id)
                .values(clave_hash=clave_hash, nombre_cifrado=nombre_cifrado, celular=celular)
            )
            usuario_id = fila.id
        else:  # CREAR
            usuario_id = uuid.uuid4()
            await self.conexion.execute(
                insert(USUARIO).values(
                    id=usuario_id,
                    correo=correo,
                    clave_hash=clave_hash,
                    nombre_cifrado=nombre_cifrado,
                    celular=celular,
                )
            )
        creada = (await self.conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))).one()
        return creada, decision

    async def otorgar_rol_acudiente(self, usuario_id: uuid.UUID, colegio_id: uuid.UUID) -> None:
        """El rol acudiente con ambito de colegio. El CHECK
        `asignacion_ambito_coherente` exige ambito_id no-nulo para 'colegio'."""
        await self.conexion.execute(
            insert(ASIGNACION_ROL).values(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                rol_codigo="acudiente",
                ambito_tipo="colegio",
                ambito_id=colegio_id,
            )
        )

    async def registrar_hijo(
        self,
        *,
        usuario_id: uuid.UUID,
        apodo: str,
        colegio_id: uuid.UUID,
        sede_id: uuid.UUID,
        grado: str,
        anio_lectivo: int,
        version_consentimiento: str,
    ) -> uuid.UUID:
        from tukit_comun.cifrado import cifrador_desde_entorno

        cifrador = cifrador_desde_entorno()
        estudiante_id = uuid.uuid4()
        matricula_id = uuid.uuid4()

        # Estudiante sin nombre en claro: el apodo cifrado vive en el vinculo,
        # no en el estudiante. `nombre_cifrado` del estudiante es NOT NULL, asi
        # que se cifra el propio apodo como marcador (el sistema nunca recibe el
        # nombre real del menor en este flujo).
        await self.conexion.execute(
            insert(ESTUDIANTE).values(id=estudiante_id, nombre_cifrado=cifrador.cifrar(apodo.encode("utf-8")))
        )
        await self.conexion.execute(
            insert(MATRICULA).values(
                id=matricula_id,
                estudiante_id=estudiante_id,
                sede_id=sede_id,
                colegio_id=colegio_id,
                grado=grado,
                anio_lectivo=anio_lectivo,
            )
        )
        await self.conexion.execute(
            insert(ACUDIENTE_MATRICULA).values(
                usuario_id=usuario_id,
                matricula_id=matricula_id,
                es_principal=True,
                apodo_cifrado=cifrador.cifrar(apodo.encode("utf-8")),
            )
        )
        # El consentimiento de menor DEBE llevar matricula_id: el CHECK
        # `consentimiento_menor_coherente` lo impone. Va en la misma
        # transaccion que el vinculo; no hay hijo sin consentimiento.
        await self.conexion.execute(
            insert(CONSENTIMIENTO).values(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                regimen="registro_menor",
                version=version_consentimiento,
                matricula_id=matricula_id,
                aceptado_en=datetime.now(UTC),
            )
        )
        return matricula_id

    async def hijos_del_padre(self, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
        """Los apodos que este titular puede ver, filtrados por las matriculas
        que alcanza. Reusa `matriculas_visibles` (Fase 1): solo lo propio."""
        from tukit_comun.cifrado import cifrador_desde_entorno

        visibles = await self.matriculas_visibles(usuario_id)
        if not visibles:
            return []
        filas = await self.conexion.execute(
            select(
                ACUDIENTE_MATRICULA.c.apodo_cifrado,
                MATRICULA.c.grado,
                MATRICULA.c.colegio_id,
            )
            .select_from(
                ACUDIENTE_MATRICULA.join(MATRICULA, MATRICULA.c.id == ACUDIENTE_MATRICULA.c.matricula_id)
            )
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                ACUDIENTE_MATRICULA.c.matricula_id.in_(visibles),
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
            )
        )
        cifrador = cifrador_desde_entorno()
        return [
            {
                "apodo": (
                    cifrador.descifrar(f.apodo_cifrado).decode("utf-8", errors="replace")
                    if f.apodo_cifrado is not None
                    else None
                ),
                "grado": f.grado,
                "colegio_id": str(f.colegio_id),
            }
            for f in filas
        ]
