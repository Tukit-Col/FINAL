"""El SQL de la revision de listas y la curaduria proactiva (ADR 0019).

`RepoAdmin` reune, atado a una conexion, cada consulta que los endpoints de
`routers/admin.py` corrian inline: leer versiones y sus renglones, escribir la
importacion de onboarding, editar/agregar/quitar renglones, cerrar (aprobar) y
clonar una version, y la cola de propuestas de curaduria. No abre ni cierra la
sesion —quien lo usa lo hace dentro de su `async with motor.sesion()`— ni alza
`ErrorDominio`: eso vive en el router, que es donde el HTTP tiene sentido. El
SQL es verbatim del que estaba en `admin_http`; esto solo lo mueve detras de un
nombre.
"""

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


class RepoAdmin:
    """Las consultas de administracion de listas y curaduria, sobre una conexion."""

    def __init__(self, conexion: Any) -> None:
        self.c = conexion

    # -- Cabecera y contexto de una version -------------------------------

    async def version_y_lista(self, version_id: uuid.UUID) -> Any:
        """La cabecera de una version con el grado/colegio de su lista, o None."""
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
        """Los `colegio_datos` de la tarea mas reciente de una version, o None."""
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

    # -- Listar versiones (cola de administracion) ------------------------

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
        ).select_from(
            LISTA.join(
                VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.numero == ultimo_numero)
            ).outerjoin(items_por_version, items_por_version.c.vid == VERSION.c.id)
        )
        if revisada is True:
            consulta = consulta.where(VERSION.c.revisada_en.is_not(None))
        elif revisada is False:
            consulta = consulta.where(VERSION.c.revisada_en.is_(None))
        if colegio_id is not None:
            consulta = consulta.where(LISTA.c.colegio_id == colegio_id)
        if grado:
            consulta = consulta.where(LISTA.c.grado == grado)
        if anio_lectivo is not None:
            consulta = consulta.where(LISTA.c.anio_lectivo == anio_lectivo)
        consulta = consulta.order_by(VERSION.c.revisada_en.is_(None).desc(), LISTA.c.grado)
        return list(await self.c.execute(consulta))

    # -- Ver revision -----------------------------------------------------

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

    # -- Ruta rapida (version revisada) -----------------------------------

    async def productos_por_conceptos(self, codigos: list[str]) -> list[Any]:
        """Los productos crudos con precio vigente de un conjunto de conceptos."""
        from .catalogo import CONCEPTO as _CONCEPTO
        from .catalogo import _consulta_productos, _precio_minimo_vigente

        precio_min = _precio_minimo_vigente()
        return list(
            await self.c.execute(_consulta_productos(precio_min).where(_CONCEPTO.c.codigo.in_(codigos)))
        )

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
                    ITEM.c.concepto_id,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                )
                .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
                .where(ITEM.c.version_id == version_id)
                .order_by(ITEM.c.orden)
            )
        )

    # -- Importar lista / sugerencia --------------------------------------

    async def cargar_conceptos(self) -> list[dict[str, Any]]:
        """El vocabulario activo, con la forma que `clasificar` consume."""
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

    # -- Evidencia (documento + percepcion) -------------------------------

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

    # -- Editar renglones -------------------------------------------------

    async def item_por_id(self, item_id: uuid.UUID, version_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(select(ITEM).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id))
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
        await self.c.execute(delete(VERSION).where(VERSION.c.id == version_id))

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

    # -- Decidir propuestas -----------------------------------------------

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

    # -- Cerrar (aprobar) una version -------------------------------------

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
                )
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()

    async def emitir_evento(self, **valores: Any) -> None:
        """Un evento en la bandeja de salida. Va en la MISMA transaccion que su
        cambio de estado (el llamador no hace commit hasta cerrar la sesion).

        Estampa el `correlacion_id` de la peticion en la carga (§A.6), para que el
        trabajo que el drenador dispare al consumir el evento herede el hilo."""
        if "carga" in valores:
            valores["carga"] = con_correlacion(valores["carga"])
        await self.c.execute(BANDEJA.insert().values(**valores))

    # -- Nueva version (clonar para corregir) -----------------------------

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

    # -- Cola de propuestas de curaduria ----------------------------------

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
                CONCEPTO.c.codigo.label("concepto_codigo"),
                CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
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

    # -- Crear concepto ---------------------------------------------------

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
