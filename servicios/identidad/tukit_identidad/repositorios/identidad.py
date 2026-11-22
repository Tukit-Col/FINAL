from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, insert, or_, select, update
from tukit_comun.bandeja import con_correlacion
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio, iso
from tukit_comun.identificadores import derivar
from tukit_comun.supresion import TITULAR_SUPRIMIDO

from ..dominio.autorizacion import Ambito
from ..dominio.matriculas import GRADOS, HijoMatricula
from ..modelos import (
    ORDEN_CLASIFICACION,
    AcudienteMatricula,
    AmbitoTipo,
    AsignacionRol,
    Base,
    Clasificacion,
    EstadoMatricula,
    Matricula,
    Permiso,
    RolPermiso,
    Sede,
)

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
    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def _cadena_de_contencion(self, ambito: Ambito) -> list[Ambito]:
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

    async def listar_colegios(self, busqueda: str | None) -> list[Any]:
        consulta = (
            select(
                COLEGIO.c.id,
                COLEGIO.c.nombre,
                COLEGIO.c.dane,
                COLEGIO.c.logo_url,
                func.count(SEDE_T.c.id).label("sedes"),
            )
            .select_from(
                COLEGIO.outerjoin(
                    SEDE_T, and_(SEDE_T.c.colegio_id == COLEGIO.c.id, SEDE_T.c.activa.is_(True))
                )
            )
            .where(COLEGIO.c.activo.is_(True))
            .group_by(COLEGIO.c.id, COLEGIO.c.nombre, COLEGIO.c.dane, COLEGIO.c.logo_url)
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
        await self.conexion.execute(
            insert(USUARIO).values(id=nuevo, correo=correo, clave_hash="sin-credencial")
        )
        return nuevo, True

    async def contacto_de(self, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(USUARIO.c.correo, USUARIO.c.activo).where(USUARIO.c.id == usuario_id)
            )
        ).one_or_none()

    async def tiene_credencial(self, usuario_id: uuid.UUID) -> bool:
        clave_hash = (
            await self.conexion.execute(select(USUARIO.c.clave_hash).where(USUARIO.c.id == usuario_id))
        ).scalar_one_or_none()
        return clave_hash is not None and clave_hash != "sin-credencial"

    async def armar_sesion(self, fila_usuario: Any) -> dict[str, Any]:
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
                "ambito": {
                    "tipo": f.ambito_tipo,
                    "id": str(f.ambito_id) if f.ambito_id is not None else None,
                },
            }
            for f in filas
        ]
        nombre = fila_usuario.correo
        if fila_usuario.nombre_cifrado is not None:
            from tukit_comun.cifrado import cifrador_desde_entorno

            nombre = (
                cifrador_desde_entorno()
                .descifrar(fila_usuario.nombre_cifrado)
                .decode("utf-8", errors="replace")
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

    async def revocar_sesiones(self, usuario_id: uuid.UUID) -> None:
        await self.conexion.execute(
            update(USUARIO)
            .where(USUARIO.c.id == usuario_id)
            .values(version_permisos=USUARIO.c.version_permisos + 1)
        )

    async def nombres_de(self, ids: list[uuid.UUID]) -> dict[str, str]:
        if not ids:
            return {}
        cifrador = cifrador_desde_entorno()
        filas = await self.conexion.execute(
            select(USUARIO.c.id, USUARIO.c.nombre_cifrado).where(
                USUARIO.c.id.in_(ids), USUARIO.c.nombre_cifrado.is_not(None)
            )
        )
        return {
            str(f.id): cifrador.descifrar(f.nombre_cifrado).decode("utf-8", errors="replace") for f in filas
        }

    async def direcciones_de(self, usuario_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(DIRECCION)
                .where(DIRECCION.c.usuario_id == usuario_id, DIRECCION.c.archivada_en.is_(None))
                .order_by(DIRECCION.c.predeterminada.desc(), DIRECCION.c.creado_en)
            )
        )

    async def limpiar_predeterminada(self, usuario_id: uuid.UUID) -> None:
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
        else:
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

    async def registrar_consentimiento_titular(self, usuario_id: uuid.UUID, version: str) -> None:
        await self.conexion.execute(
            insert(CONSENTIMIENTO).values(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                regimen="registro_titular",
                version=version,
                matricula_id=None,
                aceptado_en=datetime.now(UTC),
            )
        )

    async def hijos_del_padre(self, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
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

    async def materializar_hijos(
        self,
        usuario_id: uuid.UUID,
        hijos: list[HijoMatricula],
        anio_lectivo: int,
        cifrador: Any,
        conteo_inicial: dict[tuple[uuid.UUID, str], int] | None = None,
    ) -> int:
        conteo: dict[tuple[uuid.UUID, str], int] = dict(conteo_inicial or {})
        creados = 0
        for hijo in hijos:
            if hijo.grado not in GRADOS:
                raise ErrorDominio(
                    "grado_invalido", f"'{hijo.grado}' no es un grado escolar.", estado=422, campo="grado"
                )

            sede_id = await self.conexion.scalar(
                select(SEDE_T.c.id)
                .where(SEDE_T.c.colegio_id == hijo.colegio_id, SEDE_T.c.activa.is_(True))
                .order_by(SEDE_T.c.nombre)
                .limit(1)
            )
            if sede_id is None:
                raise ErrorDominio(
                    "colegio_sin_sede",
                    "El colegio no existe o no tiene una sede activa.",
                    estado=422,
                    campo="colegio_id",
                )

            clave = (hijo.colegio_id, hijo.grado)
            conteo[clave] = conteo.get(clave, 0) + 1
            repeticion = conteo[clave]
            if repeticion == 1:
                estudiante_id = derivar(
                    "estudiante", str(usuario_id), str(hijo.colegio_id), hijo.grado, str(anio_lectivo)
                )
            else:
                estudiante_id = derivar(
                    "estudiante",
                    str(usuario_id),
                    str(hijo.colegio_id),
                    hijo.grado,
                    str(anio_lectivo),
                    str(repeticion),
                )

            if (
                await self.conexion.scalar(select(ESTUDIANTE.c.id).where(ESTUDIANTE.c.id == estudiante_id))
                is None
            ):
                await self.conexion.execute(
                    insert(ESTUDIANTE).values(
                        id=estudiante_id,
                        nombre_cifrado=cifrador.cifrar((hijo.apodo or "").encode("utf-8")),
                    )
                )

            matricula_id = derivar(
                "matricula", str(estudiante_id), str(sede_id), hijo.grado, str(anio_lectivo)
            )
            estado_previo = await self.conexion.scalar(
                select(MATRICULA.c.estado).where(MATRICULA.c.id == matricula_id)
            )
            if estado_previo is not None and estado_previo != EstadoMatricula.ACTIVA.value:
                await self.conexion.execute(
                    update(MATRICULA)
                    .where(MATRICULA.c.id == matricula_id)
                    .values(estado=EstadoMatricula.ACTIVA.value, cerrado_en=None)
                )
                if hijo.apodo is not None:
                    await self.conexion.execute(
                        update(ESTUDIANTE)
                        .where(ESTUDIANTE.c.id == estudiante_id)
                        .values(nombre_cifrado=cifrador.cifrar(hijo.apodo.encode("utf-8")))
                    )
            if estado_previo is None:
                await self.conexion.execute(
                    insert(MATRICULA).values(
                        id=matricula_id,
                        estudiante_id=estudiante_id,
                        sede_id=sede_id,
                        colegio_id=hijo.colegio_id,
                        grado=hijo.grado,
                        anio_lectivo=anio_lectivo,
                    )
                )

            vinculo = (
                await self.conexion.execute(
                    select(ACUDIENTE_MATRICULA.c.usuario_id, ACUDIENTE_MATRICULA.c.vigente_hasta).where(
                        ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                        ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
                    )
                )
            ).one_or_none()
            if vinculo is not None and vinculo.vigente_hasta is not None:
                await self.conexion.execute(
                    update(ACUDIENTE_MATRICULA)
                    .where(
                        ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                        ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
                    )
                    .values(vigente_hasta=None)
                )
                creados += 1
            elif vinculo is None:
                await self.conexion.execute(
                    insert(ACUDIENTE_MATRICULA).values(
                        usuario_id=usuario_id,
                        matricula_id=matricula_id,
                        parentesco="acudiente",
                        es_principal=True,
                    )
                )
                creados += 1
        return creados

    async def conteo_matriculas_por_par(
        self, usuario_id: uuid.UUID, anio_lectivo: int
    ) -> dict[tuple[uuid.UUID, str], int]:
        filas = await self.conexion.execute(
            select(MATRICULA.c.colegio_id, MATRICULA.c.grado, func.count().label("n"))
            .select_from(
                ACUDIENTE_MATRICULA.join(MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id)
            )
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                MATRICULA.c.estado == "activa",
                MATRICULA.c.anio_lectivo == anio_lectivo,
            )
            .group_by(MATRICULA.c.colegio_id, MATRICULA.c.grado)
        )
        return {(uuid.UUID(str(f.colegio_id)), f.grado): int(f.n) for f in filas}

    async def matriculas_del_titular(self, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
        cifrador = cifrador_desde_entorno()
        filas = await self.conexion.execute(
            select(
                MATRICULA.c.id,
                MATRICULA.c.colegio_id,
                MATRICULA.c.grado,
                MATRICULA.c.anio_lectivo,
                ESTUDIANTE.c.nombre_cifrado,
            )
            .select_from(
                ACUDIENTE_MATRICULA.join(
                    MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id
                ).join(ESTUDIANTE, MATRICULA.c.estudiante_id == ESTUDIANTE.c.id)
            )
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                MATRICULA.c.estado == "activa",
            )
            .order_by(MATRICULA.c.colegio_id, MATRICULA.c.grado)
        )
        matriculas = []
        for f in filas:
            apodo = cifrador.descifrar(f.nombre_cifrado).decode("utf-8", errors="replace")
            matriculas.append(
                {
                    "matricula_id": str(f.id),
                    "colegio_id": str(f.colegio_id),
                    "grado": f.grado,
                    "anio_lectivo": int(f.anio_lectivo),
                    "apodo": apodo or None,
                }
            )
        return matriculas

    async def matricula_del_portador(self, usuario_id: uuid.UUID, matricula_id: uuid.UUID) -> Any:
        fila = (
            await self.conexion.execute(
                select(MATRICULA.c.id, MATRICULA.c.estudiante_id, ESTUDIANTE.c.nombre_cifrado)
                .select_from(
                    ACUDIENTE_MATRICULA.join(
                        MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id
                    ).join(ESTUDIANTE, MATRICULA.c.estudiante_id == ESTUDIANTE.c.id)
                )
                .where(
                    ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                    ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
                    ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                    MATRICULA.c.estado == EstadoMatricula.ACTIVA.value,
                )
            )
        ).one_or_none()
        if fila is None:
            raise ErrorDominio("hijo_no_existe", "Ese hijo no está en tu cuenta.", estado=404)
        return fila

    async def retirar_matricula(self, usuario_id: uuid.UUID, matricula_id: uuid.UUID) -> None:
        ahora = datetime.now(UTC)
        await self.conexion.execute(
            update(ACUDIENTE_MATRICULA)
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
            )
            .values(vigente_hasta=ahora)
        )
        otros = await self.conexion.scalar(
            select(func.count())
            .select_from(ACUDIENTE_MATRICULA)
            .where(
                ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
            )
        )
        if not otros:
            await self.conexion.execute(
                update(MATRICULA)
                .where(MATRICULA.c.id == matricula_id)
                .values(estado=EstadoMatricula.RETIRADA.value, cerrado_en=ahora)
            )

    async def es_staff_vigente(self, usuario_id: uuid.UUID) -> bool:
        ahora = datetime.now(UTC)
        existe = await self.conexion.scalar(
            select(ASIGNACION_ROL.c.id)
            .where(
                ASIGNACION_ROL.c.usuario_id == usuario_id,
                ASIGNACION_ROL.c.rol_codigo.in_(("admin", "operador")),
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
            .limit(1)
        )
        return existe is not None

    async def padron_acudientes(self, ids: list[uuid.UUID] | None) -> list[dict[str, Any]]:
        ahora = datetime.now(UTC)
        roles_internos = ("admin", "operador", "colegio_admin", "colegio_docente")
        sin_rol_interno = ~(
            select(ASIGNACION_ROL.c.id)
            .where(
                ASIGNACION_ROL.c.usuario_id == USUARIO.c.id,
                ASIGNACION_ROL.c.rol_codigo.in_(roles_internos),
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
            .exists()
        )
        consulta = (
            select(USUARIO.c.id, USUARIO.c.correo, USUARIO.c.celular, USUARIO.c.creado_en)
            .where(
                USUARIO.c.clave_hash != "sin-credencial",
                USUARIO.c.activo.is_(True),
                sin_rol_interno,
            )
            .order_by(USUARIO.c.creado_en.desc())
        )
        if ids is not None:
            consulta = consulta.where(USUARIO.c.id.in_(ids))
        usuarios = list(await self.conexion.execute(consulta))

        hijos_por_usuario: dict[uuid.UUID, list[dict[str, Any]]] = {}
        if usuarios:
            cifrador = cifrador_desde_entorno()
            filas_hijos = await self.conexion.execute(
                select(
                    ACUDIENTE_MATRICULA.c.usuario_id,
                    ESTUDIANTE.c.nombre_cifrado,
                    MATRICULA.c.colegio_id,
                    MATRICULA.c.grado,
                    COLEGIO.c.nombre,
                )
                .select_from(
                    ACUDIENTE_MATRICULA.join(MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id)
                    .join(ESTUDIANTE, MATRICULA.c.estudiante_id == ESTUDIANTE.c.id)
                    .join(COLEGIO, MATRICULA.c.colegio_id == COLEGIO.c.id)
                )
                .where(
                    ACUDIENTE_MATRICULA.c.usuario_id.in_([u.id for u in usuarios]),
                    ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                    MATRICULA.c.estado == "activa",
                )
                .order_by(ACUDIENTE_MATRICULA.c.usuario_id, MATRICULA.c.grado)
            )
            for h in filas_hijos:
                apodo = cifrador.descifrar(h.nombre_cifrado).decode("utf-8", errors="replace")
                hijos_por_usuario.setdefault(h.usuario_id, []).append(
                    {
                        "apodo": apodo or None,
                        "colegio_id": str(h.colegio_id),
                        "colegio_nombre": h.nombre,
                        "grado": h.grado,
                    }
                )

        return [
            {
                "usuario_id": str(u.id),
                "correo": u.correo,
                "celular": u.celular,
                "creado_en": iso(u.creado_en),
                "hijos": hijos_por_usuario.get(u.id, []),
            }
            for u in usuarios
        ]

    async def registrar_acudiente_con_hijos(
        self,
        correo: str,
        clave: str,
        celular: str | None,
        hijos: list[HijoMatricula],
        anio_lectivo: int,
        cifrador: Any,
    ) -> tuple[uuid.UUID, bool]:
        from ..dominio.sesiones import hashear_clave

        existente = (
            await self.conexion.execute(
                select(USUARIO.c.id, USUARIO.c.clave_hash).where(USUARIO.c.correo == correo)
            )
        ).one_or_none()

        if existente is not None and existente.clave_hash != "sin-credencial":
            return existente.id, False

        if existente is None:
            usuario_id = derivar("usuario", correo)
            if await self.conexion.scalar(select(USUARIO.c.id).where(USUARIO.c.id == usuario_id)):
                usuario_id = uuid.uuid4()
            await self.conexion.execute(
                insert(USUARIO).values(
                    id=usuario_id,
                    correo=correo,
                    clave_hash=hashear_clave(clave),
                    celular=celular,
                )
            )
        else:
            usuario_id = existente.id
            await self.conexion.execute(
                update(USUARIO)
                .where(USUARIO.c.id == usuario_id)
                .values(clave_hash=hashear_clave(clave), celular=celular)
            )

        await self.materializar_hijos(usuario_id, hijos, anio_lectivo, cifrador)
        return usuario_id, True

    async def consentimientos_de(self, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
        filas = await self.conexion.execute(
            select(CONSENTIMIENTO)
            .where(CONSENTIMIENTO.c.usuario_id == usuario_id)
            .order_by(CONSENTIMIENTO.c.aceptado_en)
        )
        return [
            {
                "regimen": f.regimen,
                "version": f.version,
                "matricula_id": str(f.matricula_id) if f.matricula_id is not None else None,
                "aceptado_en": iso(f.aceptado_en),
                "revocado_en": iso(f.revocado_en) if f.revocado_en is not None else None,
            }
            for f in filas
        ]

    async def revocar_consentimientos(self, usuario_id: uuid.UUID, ahora: datetime) -> int:
        r = await self.conexion.execute(
            update(CONSENTIMIENTO)
            .where(CONSENTIMIENTO.c.usuario_id == usuario_id, CONSENTIMIENTO.c.revocado_en.is_(None))
            .values(revocado_en=ahora)
        )
        return int(r.rowcount or 0)

    async def suprimir_titular(self, usuario_id: uuid.UUID, *, correo_nuevo: str) -> uuid.UUID:
        from ..dominio.sesiones import hashear_clave

        ahora = datetime.now(UTC)
        tablas = Base.metadata.tables
        cifrador = cifrador_desde_entorno()

        vinculos = list(
            await self.conexion.execute(
                select(
                    ACUDIENTE_MATRICULA.c.matricula_id,
                    ACUDIENTE_MATRICULA.c.vigente_hasta,
                    MATRICULA.c.estudiante_id,
                )
                .select_from(
                    ACUDIENTE_MATRICULA.join(MATRICULA, MATRICULA.c.id == ACUDIENTE_MATRICULA.c.matricula_id)
                )
                .where(ACUDIENTE_MATRICULA.c.usuario_id == usuario_id)
            )
        )
        await self.conexion.execute(
            update(ACUDIENTE_MATRICULA)
            .where(ACUDIENTE_MATRICULA.c.usuario_id == usuario_id)
            .values(apodo_cifrado=None)
        )
        for v in vinculos:
            if v.vigente_hasta is None:
                await self.retirar_matricula(usuario_id, v.matricula_id)
        for estudiante_id in {v.estudiante_id for v in vinculos}:
            acompanado = await self.conexion.scalar(
                select(func.count())
                .select_from(
                    ACUDIENTE_MATRICULA.join(MATRICULA, MATRICULA.c.id == ACUDIENTE_MATRICULA.c.matricula_id)
                )
                .where(
                    MATRICULA.c.estudiante_id == estudiante_id,
                    ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                )
            )
            if not acompanado:
                await self.conexion.execute(
                    update(ESTUDIANTE)
                    .where(ESTUDIANTE.c.id == estudiante_id)
                    .values(nombre_cifrado=cifrador.cifrar(b""), documento_hash=None, fecha_nacimiento=None)
                )

        await self.conexion.execute(DIRECCION.delete().where(DIRECCION.c.usuario_id == usuario_id))
        await self.conexion.execute(
            tablas["perfil_socioeconomico"]
            .delete()
            .where(tablas["perfil_socioeconomico"].c.usuario_id == usuario_id)
        )
        await self.revocar_consentimientos(usuario_id, ahora)
        await self.conexion.execute(
            update(USUARIO)
            .where(USUARIO.c.id == usuario_id)
            .values(
                correo=correo_nuevo,
                clave_hash=hashear_clave(uuid.uuid4().hex + uuid.uuid4().hex),
                nombre_cifrado=None,
                celular=None,
                activo=False,
                anonimizado_en=ahora,
                version_permisos=USUARIO.c.version_permisos + 1,
            )
        )

        solicitud_id = uuid.uuid4()
        await self.conexion.execute(
            insert(tablas["solicitud_supresion"]).values(
                id=solicitud_id,
                usuario_id=usuario_id,
                estado="propagando",
                suscriptores_confirmados=[],
                creado_en=ahora,
            )
        )
        await self.conexion.execute(
            insert(tablas["bandeja_salida"]).values(
                tipo=TITULAR_SUPRIMIDO,
                agregado_tipo="solicitud_supresion",
                agregado_id=solicitud_id,
                carga=con_correlacion(
                    {
                        "usuario_id": str(usuario_id),
                        "solicitud_id": str(solicitud_id),
                        "suprimido_en": iso(ahora),
                    }
                ),
                creado_en=ahora,
            )
        )
        return solicitud_id
