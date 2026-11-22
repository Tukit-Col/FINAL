from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, delete, func, select, update
from tukit_comun.bandeja import con_correlacion

from ..modelos import Base

CONCEPTO = Base.metadata.tables["concepto"]
LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
ITEM = Base.metadata.tables["item_lista_oficial"]
PROPUESTA = Base.metadata.tables["propuesta_producto"]
TAREA = Base.metadata.tables["tarea_importacion"]
TIENDA = Base.metadata.tables["tienda"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
CORRECCION = Base.metadata.tables["correccion_lista"]


class RepoAdmin:

    def __init__(self, conexion: Any) -> None:
        self.c = conexion

    async def version_y_lista(self, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(
                    VERSION.c.id,
                    VERSION.c.numero,
                    VERSION.c.revisada_en,
                    VERSION.c.lista_id,
                    LISTA.c.colegio_id,
                    LISTA.c.grado,
                    LISTA.c.anio_lectivo,
                )
                .select_from(VERSION.join(LISTA, LISTA.c.id == VERSION.c.lista_id))
                .where(VERSION.c.id == version_id)
            )
        ).first()

    async def colegio_datos_de(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        fila = (
            await self.c.execute(
                select(TAREA.c.colegio_datos)
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()
        if fila is None or fila.colegio_datos is None:
            return None
        return dict(fila.colegio_datos)

    async def concepto_id_por_codigo(self, codigo: str) -> uuid.UUID | None:
        return (
            await self.c.execute(select(CONCEPTO.c.id).where(CONCEPTO.c.codigo == codigo))
        ).scalar_one_or_none()

    async def nombre_concepto(self, concepto_id: uuid.UUID) -> str:
        return (
            await self.c.execute(select(CONCEPTO.c.nombre_canonico).where(CONCEPTO.c.id == concepto_id))
        ).scalar_one()

    async def listar_versiones(
        self,
        *,
        revisada: bool | None,
        colegio_id: uuid.UUID | None,
        grado: str | None,
        anio_lectivo: int | None,
    ) -> list[Any]:
        ultimo_numero = (
            select(func.max(VERSION.c.numero))
            .where(VERSION.c.lista_id == LISTA.c.id)
            .correlate(LISTA)
            .scalar_subquery()
        )
        items_por_version = (
            select(ITEM.c.version_id.label("vid"), func.count().label("renglones"))
            .group_by(ITEM.c.version_id)
            .subquery()
        )
        tarea_reciente = (
            select(TAREA.c.id)
            .where(TAREA.c.version_id == VERSION.c.id)
            .order_by(TAREA.c.creada_en.desc())
            .limit(1)
            .correlate(VERSION)
            .scalar_subquery()
        )
        procedencia = select(TAREA.c.origen).where(TAREA.c.id == tarea_reciente).scalar_subquery()
        contacto = select(TAREA.c.contacto_referencia).where(TAREA.c.id == tarea_reciente).scalar_subquery()
        colegio_datos = select(TAREA.c.colegio_datos).where(TAREA.c.id == tarea_reciente).scalar_subquery()
        tareas_de_version = select(TAREA.c.id).where(TAREA.c.version_id == VERSION.c.id).correlate(VERSION)
        retirada = and_(
            tareas_de_version.where(TAREA.c.retirada_en.is_not(None)).exists(),
            ~tareas_de_version.where(TAREA.c.retirada_en.is_(None)).exists(),
        )
        consulta = select(
            LISTA.c.id.label("lista_id"),
            LISTA.c.colegio_id,
            LISTA.c.grado,
            LISTA.c.anio_lectivo,
            VERSION.c.id.label("version_id"),
            VERSION.c.numero,
            VERSION.c.revisada_en,
            func.coalesce(items_por_version.c.renglones, 0).label("renglones"),
            procedencia.label("procedencia"),
            contacto.label("contacto_referencia"),
            colegio_datos.label("colegio_datos"),
            retirada.label("retirada_por_acudiente"),
        ).select_from(
            LISTA.join(
                VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.numero == ultimo_numero)
            ).outerjoin(items_por_version, items_por_version.c.vid == VERSION.c.id)
        )
        if revisada is True:
            consulta = consulta.where(VERSION.c.revisada_en.is_not(None))
        elif revisada is False:
            consulta = consulta.where(VERSION.c.revisada_en.is_(None), ~retirada)
        if colegio_id is not None:
            consulta = consulta.where(LISTA.c.colegio_id == colegio_id)
        if grado:
            consulta = consulta.where(LISTA.c.grado == grado)
        if anio_lectivo is not None:
            consulta = consulta.where(LISTA.c.anio_lectivo == anio_lectivo)
        consulta = consulta.order_by(VERSION.c.revisada_en.is_(None).desc(), LISTA.c.grado)
        return list(await self.c.execute(consulta))

    async def items_de_revision(self, version_id: uuid.UUID) -> list[Any]:
        return list(
            await self.c.execute(
                select(
                    ITEM.c.id,
                    ITEM.c.orden,
                    ITEM.c.texto_original,
                    ITEM.c.cantidad,
                    ITEM.c.unidad,
                    ITEM.c.tipo_item,
                    ITEM.c.modo_adquisicion,
                    ITEM.c.instruccion_colegio,
                    ITEM.c.url_externa,
                    ITEM.c.atributos,
                    ITEM.c.requiere_revision,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                )
                .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
                .where(ITEM.c.version_id == version_id)
                .order_by(ITEM.c.orden)
            )
        )

    async def propuestas_pendientes_de_version(self, version_id: uuid.UUID) -> list[Any]:
        return list(
            await self.c.execute(
                select(
                    PROPUESTA.c.id,
                    PROPUESTA.c.texto_origen,
                    PROPUESTA.c.item_lista_id,
                    PROPUESTA.c.nombre,
                    PROPUESTA.c.marca,
                    PROPUESTA.c.imagen_url,
                    PROPUESTA.c.precio_centavos,
                    PROPUESTA.c.nivel_sugerido,
                    PROPUESTA.c.concepto_sugerido,
                    PROPUESTA.c.puntaje,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                )
                .select_from(PROPUESTA.outerjoin(CONCEPTO, CONCEPTO.c.id == PROPUESTA.c.concepto_id))
                .where(PROPUESTA.c.version_lista_id == version_id, PROPUESTA.c.estado == "pendiente")
                .order_by(PROPUESTA.c.propuesta_en)
            )
        )

    async def productos_por_conceptos(self, codigos: list[str]) -> list[Any]:
        from .catalogo import CONCEPTO as _CONCEPTO
        from .catalogo import _consulta_productos, _precio_minimo_vigente

        precio_min = _precio_minimo_vigente()
        return list(
            await self.c.execute(_consulta_productos(precio_min).where(_CONCEPTO.c.codigo.in_(codigos)))
        )

    async def reglas_por_codigo(self, codigos: list[str]) -> dict[str, tuple[tuple[str, ...], bool, str]]:
        if not codigos:
            return {}
        filas = await self.c.execute(
            select(
                CONCEPTO.c.codigo,
                CONCEPTO.c.atributos_discriminantes,
                CONCEPTO.c.uno_por_estudiante,
                CONCEPTO.c.tipo_item,
            ).where(CONCEPTO.c.codigo.in_(codigos))
        )
        return {
            f.codigo: (tuple(f.atributos_discriminantes or ()), bool(f.uno_por_estudiante), f.tipo_item)
            for f in filas
        }

    async def discriminantes_de_concepto(self, concepto_id: uuid.UUID | None) -> tuple[str, ...]:
        if concepto_id is None:
            return ()
        valor = await self.c.scalar(
            select(CONCEPTO.c.atributos_discriminantes).where(CONCEPTO.c.id == concepto_id)
        )
        return tuple(valor or ())

    async def descartar_aviso(self, item_id: uuid.UUID, version_id: uuid.UUID, clave: str) -> bool:
        actual = await self.c.scalar(
            select(ITEM.c.avisos_descartados).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id)
        )
        if actual is None:
            return False
        if clave not in actual:
            await self.c.execute(
                update(ITEM).where(ITEM.c.id == item_id).values(avisos_descartados=[*actual, clave])
            )
        return True

    async def items_resueltos(self, version_id: uuid.UUID) -> list[Any]:
        return list(
            await self.c.execute(
                select(
                    ITEM.c.id,
                    ITEM.c.orden,
                    ITEM.c.texto_original,
                    ITEM.c.cantidad,
                    ITEM.c.tipo_item,
                    ITEM.c.modo_adquisicion,
                    ITEM.c.instruccion_colegio,
                    ITEM.c.url_externa,
                    ITEM.c.atributos,
                    ITEM.c.avisos_descartados,
                    ITEM.c.concepto_id,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                )
                .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
                .where(ITEM.c.version_id == version_id)
                .order_by(ITEM.c.orden)
            )
        )

    async def cargar_conceptos(self) -> list[dict[str, Any]]:
        filas = await self.c.execute(
            select(CONCEPTO.c.id, CONCEPTO.c.nombre_canonico, CONCEPTO.c.sinonimos).where(CONCEPTO.c.activo)
        )
        return [
            {"id": f.id, "nombre": f.nombre_canonico, "sinonimos": list(f.sinonimos or ())} for f in filas
        ]

    async def lista_por_llave(self, colegio_id: uuid.UUID, grado: str, anio_lectivo: int) -> Any:
        return (
            await self.c.execute(
                select(LISTA.c.id).where(
                    LISTA.c.colegio_id == colegio_id,
                    LISTA.c.grado == grado,
                    LISTA.c.anio_lectivo == anio_lectivo,
                )
            )
        ).first()

    async def crear_lista(
        self, lista_id: uuid.UUID, colegio_id: uuid.UUID, grado: str, anio_lectivo: int
    ) -> None:
        await self.c.execute(
            LISTA.insert().values(id=lista_id, colegio_id=colegio_id, grado=grado, anio_lectivo=anio_lectivo)
        )

    async def max_numero_version(self, lista_id: uuid.UUID) -> int:
        ultimo = (
            await self.c.execute(select(func.max(VERSION.c.numero)).where(VERSION.c.lista_id == lista_id))
        ).scalar_one_or_none()
        return int(ultimo or 0)

    async def desvigar_versiones(self, lista_id: uuid.UUID) -> None:
        await self.c.execute(
            update(VERSION)
            .where(VERSION.c.lista_id == lista_id, VERSION.c.vigente.is_(True))
            .values(vigente=False)
        )

    async def crear_version(
        self, version_id: uuid.UUID, lista_id: uuid.UUID, numero: int, *, vigente: bool
    ) -> None:
        await self.c.execute(
            VERSION.insert().values(
                id=version_id, lista_id=lista_id, numero=numero, vigente=vigente, revisada_en=None
            )
        )

    async def crear_item(self, **valores: Any) -> None:
        await self.c.execute(ITEM.insert().values(**valores))

    async def crear_tarea(self, **valores: Any) -> None:
        await self.c.execute(TAREA.insert().values(**valores))

    async def importacion_por_clave(self, clave: uuid.UUID) -> dict[str, Any] | None:
        fila = (
            await self.c.execute(
                select(TAREA.c.id, TAREA.c.version_id, VERSION.c.revisada_en)
                .join(VERSION, VERSION.c.id == TAREA.c.version_id)
                .where(TAREA.c.clave_idempotencia == clave)
            )
        ).first()
        if fila is None:
            return None
        items = (
            await self.c.execute(
                select(func.count()).select_from(ITEM).where(ITEM.c.version_id == fila.version_id)
            )
        ).scalar_one()
        return {
            "version_id": str(fila.version_id),
            "tarea_id": str(fila.id),
            "items": int(items),
            "revisada": fila.revisada_en is not None,
        }

    async def listar_sugerencias(self) -> list[Any]:
        return list(
            await self.c.execute(
                select(
                    TAREA.c.id,
                    TAREA.c.estado,
                    TAREA.c.colegio_id,
                    TAREA.c.grado,
                    TAREA.c.anio_lectivo,
                    TAREA.c.contacto_referencia,
                    TAREA.c.documento.is_not(None).label("tiene_documento"),
                )
                .where(TAREA.c.origen == "sugerencia_padre")
                .order_by(TAREA.c.creada_en.desc())
            )
        )

    async def tarea_con_evidencia(self, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(TAREA.c.documento, TAREA.c.percepcion_cruda)
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
            )
        ).first()

    async def items_percepcion(self, version_id: uuid.UUID) -> list[Any]:
        return list(
            await self.c.execute(
                select(ITEM.c.texto_original, ITEM.c.cantidad, ITEM.c.confianza_normalizacion)
                .where(ITEM.c.version_id == version_id)
                .order_by(ITEM.c.orden)
            )
        )

    async def registrar_correccion(self, **valores: Any) -> None:
        await self.c.execute(CORRECCION.insert().values(id=uuid.uuid4(), **valores))

    async def correcciones(
        self, *, desde: Any = None, campo: str | None = None, limite: int = 200
    ) -> list[Any]:
        q = select(CORRECCION).order_by(CORRECCION.c.creado_en.desc()).limit(limite)
        if desde is not None:
            q = q.where(CORRECCION.c.creado_en >= desde)
        if campo:
            q = q.where(CORRECCION.c.campo == campo)
        return list(await self.c.execute(q))

    async def correcciones_por_campo(self) -> dict[str, int]:
        filas = await self.c.execute(select(CORRECCION.c.campo, func.count()).group_by(CORRECCION.c.campo))
        return {str(c): int(n) for c, n in filas}

    async def codigo_de_concepto(self, concepto_id: uuid.UUID | None) -> str | None:
        if concepto_id is None:
            return None
        return await self.c.scalar(select(CONCEPTO.c.codigo).where(CONCEPTO.c.id == concepto_id))

    async def aprender_sinonimo(
        self, sinonimo: str, concepto_id: uuid.UUID, anterior_id: uuid.UUID | None
    ) -> bool:
        actuales = list(
            await self.c.scalar(select(CONCEPTO.c.sinonimos).where(CONCEPTO.c.id == concepto_id)) or []
        )
        agregado = sinonimo not in actuales
        if agregado:
            await self.c.execute(
                update(CONCEPTO).where(CONCEPTO.c.id == concepto_id).values(sinonimos=[*actuales, sinonimo])
            )
        if anterior_id is not None and anterior_id != concepto_id:
            viejos = list(
                await self.c.scalar(select(CONCEPTO.c.sinonimos).where(CONCEPTO.c.id == anterior_id)) or []
            )
            if sinonimo in viejos:
                await self.c.execute(
                    update(CONCEPTO)
                    .where(CONCEPTO.c.id == anterior_id)
                    .values(sinonimos=[s for s in viejos if s != sinonimo])
                )
        return agregado

    async def cerrar_avisos_de_version(
        self, version_id: uuid.UUID, claves_por_item: dict[uuid.UUID, list[str]]
    ) -> int:
        cerrados = 0
        for item_id, claves in claves_por_item.items():
            actual = list(
                await self.c.scalar(
                    select(ITEM.c.avisos_descartados).where(
                        ITEM.c.id == item_id, ITEM.c.version_id == version_id
                    )
                )
                or []
            )
            nuevos = [c for c in claves if c not in actual]
            if nuevos:
                await self.c.execute(
                    update(ITEM).where(ITEM.c.id == item_id).values(avisos_descartados=[*actual, *nuevos])
                )
                cerrados += len(nuevos)
        return cerrados

    async def item_por_id(self, item_id: uuid.UUID, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(select(ITEM).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id))
        ).first()

    async def item_por_orden(self, version_id: uuid.UUID, orden: int) -> Any:
        return (
            await self.c.execute(select(ITEM).where(ITEM.c.version_id == version_id, ITEM.c.orden == orden))
        ).first()

    async def actualizar_item(self, item_id: uuid.UUID, valores: dict[str, Any]) -> None:
        await self.c.execute(update(ITEM).where(ITEM.c.id == item_id).values(**valores))

    async def max_orden_item(self, version_id: uuid.UUID) -> int:
        ultimo = (
            await self.c.execute(select(func.max(ITEM.c.orden)).where(ITEM.c.version_id == version_id))
        ).scalar_one_or_none()
        return int(ultimo or 0)

    async def borrar_item(self, item_id: uuid.UUID, version_id: uuid.UUID) -> int:
        resultado = await self.c.execute(
            delete(ITEM).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id)
        )
        return int(resultado.rowcount)

    async def borrar_version(self, version_id: uuid.UUID) -> None:
        version = (
            await self.c.execute(
                select(VERSION.c.lista_id, VERSION.c.vigente).where(VERSION.c.id == version_id)
            )
        ).one()
        await self.c.execute(delete(TAREA).where(TAREA.c.version_id == version_id))
        await self.c.execute(delete(VERSION).where(VERSION.c.id == version_id))

        restantes = list(
            await self.c.execute(
                select(VERSION.c.id, VERSION.c.revisada_en)
                .where(VERSION.c.lista_id == version.lista_id)
                .order_by(VERSION.c.numero.desc())
            )
        )
        if not restantes:
            await self.c.execute(delete(TAREA).where(TAREA.c.lista_id == version.lista_id))
            await self.c.execute(delete(LISTA).where(LISTA.c.id == version.lista_id))
        elif version.vigente:
            heredera = next((r for r in restantes if r.revisada_en is not None), restantes[0])
            await self.c.execute(update(VERSION).where(VERSION.c.id == heredera.id).values(vigente=True))

    async def tarea_colegio_datos(self, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(TAREA.c.id, TAREA.c.colegio_datos)
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()

    async def actualizar_colegio_datos(self, tarea_id: uuid.UUID, datos: dict[str, Any]) -> None:
        await self.c.execute(update(TAREA).where(TAREA.c.id == tarea_id).values(colegio_datos=datos))

    async def propuesta_estado(self, prop_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(select(PROPUESTA.c.id, PROPUESTA.c.estado).where(PROPUESTA.c.id == prop_id))
        ).first()

    async def rechazar_propuesta(self, prop_id: uuid.UUID, motivo: Any, resuelta_en: Any) -> None:
        await self.c.execute(
            update(PROPUESTA)
            .where(PROPUESTA.c.id == prop_id)
            .values(estado="rechazada", motivo=motivo, resuelta_en=resuelta_en)
        )

    async def contar_propuestas_pendientes(self, version_id: uuid.UUID) -> int:
        return (
            await self.c.execute(
                select(func.count())
                .select_from(PROPUESTA)
                .where(PROPUESTA.c.version_lista_id == version_id, PROPUESTA.c.estado == "pendiente")
            )
        ).scalar_one()

    async def marcar_revisada(self, version_id: uuid.UUID, revisada_en: Any) -> None:
        await self.c.execute(
            update(VERSION).where(VERSION.c.id == version_id).values(revisada_en=revisada_en)
        )

    async def promover_vigente(self, version_id: uuid.UUID) -> None:
        await self.c.execute(update(VERSION).where(VERSION.c.id == version_id).values(vigente=True))

    async def tarea_para_evento(self, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(
                    TAREA.c.id,
                    TAREA.c.contacto_referencia,
                    TAREA.c.preferencias,
                    TAREA.c.colegio_datos,
                    TAREA.c.referencias,
                )
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()

    async def emitir_evento(self, **valores: Any) -> None:
        if "carga" in valores:
            valores["carga"] = con_correlacion(valores["carga"])
        await self.c.execute(BANDEJA.insert().values(**valores))

    async def version_vigente(self, lista_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(VERSION.c.id, VERSION.c.numero, VERSION.c.revisada_en).where(
                    VERSION.c.lista_id == lista_id, VERSION.c.vigente.is_(True)
                )
            )
        ).first()

    async def items_para_clonar(self, version_id: uuid.UUID) -> list[Any]:
        return list(
            await self.c.execute(
                select(
                    ITEM.c.orden,
                    ITEM.c.texto_original,
                    ITEM.c.concepto_id,
                    ITEM.c.cantidad,
                    ITEM.c.unidad,
                    ITEM.c.tipo_item,
                    ITEM.c.modo_adquisicion,
                    ITEM.c.instruccion_colegio,
                    ITEM.c.url_externa,
                    ITEM.c.atributos,
                    ITEM.c.requiere_revision,
                    ITEM.c.avisos_descartados,
                ).where(ITEM.c.version_id == version_id)
            )
        )

    async def tarea_origen(self, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(
                    TAREA.c.origen,
                    TAREA.c.documento,
                    TAREA.c.percepcion_cruda,
                    TAREA.c.colegio_datos,
                    TAREA.c.colegio_id,
                    TAREA.c.grado,
                    TAREA.c.anio_lectivo,
                )
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()

    async def cola_propuestas(self, concepto: str | None) -> list[Any]:
        consulta = (
            select(
                PROPUESTA.c.id,
                PROPUESTA.c.texto_origen,
                PROPUESTA.c.nombre,
                PROPUESTA.c.marca,
                PROPUESTA.c.imagen_url,
                PROPUESTA.c.precio_centavos,
                PROPUESTA.c.nivel_sugerido,
                PROPUESTA.c.concepto_sugerido,
                PROPUESTA.c.puntaje,
                PROPUESTA.c.origen,
                PROPUESTA.c.especificaciones,
                CONCEPTO.c.codigo.label("concepto_codigo"),
                CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                CONCEPTO.c.atributos_discriminantes,
                CONCEPTO.c.atributos_descriptivos,
            )
            .select_from(PROPUESTA.outerjoin(CONCEPTO, CONCEPTO.c.id == PROPUESTA.c.concepto_id))
            .where(PROPUESTA.c.estado == "pendiente")
            .order_by(PROPUESTA.c.propuesta_en)
        )
        if concepto:
            consulta = consulta.where(CONCEPTO.c.codigo == concepto)
        return list(await self.c.execute(consulta))

    async def tienda_id_por_slug(self, slug: str) -> uuid.UUID | None:
        return (await self.c.execute(select(TIENDA.c.id).where(TIENDA.c.slug == slug))).scalar_one_or_none()

    async def concepto_codigo_por_nombre(self, nombre_lower: str) -> str | None:
        return (
            await self.c.execute(
                select(CONCEPTO.c.codigo).where(func.lower(CONCEPTO.c.nombre_canonico) == nombre_lower)
            )
        ).scalar_one_or_none()

    async def codigos_concepto(self) -> list[str]:
        return [c for (c,) in await self.c.execute(select(CONCEPTO.c.codigo)) if c and c.startswith("C")]

    async def crear_concepto(self, **valores: Any) -> None:
        await self.c.execute(CONCEPTO.insert().values(**valores))
