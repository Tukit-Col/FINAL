from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, update
from tukit_comun.texto import normalizar_personaje

from ..modelos import Base
from ..modelos.base import CALIDAD_POR_NIVEL

CONCEPTO = Base.metadata.tables["concepto"]
PRODUCTO = Base.metadata.tables["producto_canonico"]
TIENDA = Base.metadata.tables["tienda"]
OFERTA = Base.metadata.tables["oferta_tienda"]
PRECIO = Base.metadata.tables["precio_oferta"]
LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
ITEM = Base.metadata.tables["item_lista_oficial"]
TAREA = Base.metadata.tables["tarea_importacion"]

_ORDEN_NIVEL = ("economico", "confiable", "premium")

UMBRAL_SIN_REVISAR = min(CALIDAD_POR_NIVEL.values())


def _precio_minimo_vigente() -> Any:
    return (
        select(
            OFERTA.c.producto_canonico_id.label("pid"),
            func.min(PRECIO.c.valor_centavos).label("centavos"),
            func.count(func.distinct(OFERTA.c.tienda_id)).label("tiendas"),
        )
        .select_from(OFERTA.join(PRECIO, PRECIO.c.oferta_id == OFERTA.c.id))
        .where(OFERTA.c.activo.is_(True), PRECIO.c.vigente_hasta.is_(None))
        .group_by(OFERTA.c.producto_canonico_id)
        .subquery()
    )


def _paginar(consulta: Select, pagina: int, por_pagina: int) -> Select:
    return consulta.limit(por_pagina).offset((pagina - 1) * por_pagina)


def _consulta_productos(precio_min: Any) -> Select:
    return (
        select(
            PRODUCTO.c.id,
            PRODUCTO.c.sku_interno,
            PRODUCTO.c.ean,
            PRODUCTO.c.es_propio,
            PRODUCTO.c.nombre,
            PRODUCTO.c.descripcion,
            PRODUCTO.c.marca,
            PRODUCTO.c.nivel,
            PRODUCTO.c.personaje,
            PRODUCTO.c.imagen_url,
            PRODUCTO.c.unidad_base,
            PRODUCTO.c.unidades_por_empaque,
            PRODUCTO.c.atributos,
            PRODUCTO.c.quality_score,
            CONCEPTO.c.codigo.label("concepto_codigo"),
            CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
            precio_min.c.centavos,
            precio_min.c.tiendas,
        )
        .select_from(
            PRODUCTO.join(CONCEPTO, CONCEPTO.c.id == PRODUCTO.c.concepto_id).outerjoin(
                precio_min, precio_min.c.pid == PRODUCTO.c.id
            )
        )
        .where(PRODUCTO.c.activo.is_(True))
    )


def _consulta_ofertas(producto_ids: list[Any]) -> Select:
    return (
        select(
            OFERTA.c.producto_canonico_id.label("pid"),
            TIENDA.c.slug,
            TIENDA.c.nombre.label("tienda_nombre"),
            TIENDA.c.tipo,
            OFERTA.c.url,
            OFERTA.c.disponible,
            OFERTA.c.metodo_vinculacion,
            OFERTA.c.confianza_vinculacion,
            PRECIO.c.valor_centavos,
            PRECIO.c.vigente_desde,
            PRECIO.c.vigente_hasta,
            PRECIO.c.fuente,
        )
        .select_from(
            OFERTA.join(TIENDA, TIENDA.c.id == OFERTA.c.tienda_id).outerjoin(
                PRECIO,
                and_(PRECIO.c.oferta_id == OFERTA.c.id, PRECIO.c.vigente_hasta.is_(None)),
            )
        )
        .where(OFERTA.c.producto_canonico_id.in_(producto_ids), OFERTA.c.activo.is_(True))
    )


_ACENTOS = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"}


def _normalizar_personaje(texto: str) -> str:
    return normalizar_personaje(texto)


def _normalizado_sql(columna: Any) -> Any:
    expr = func.lower(columna)
    for con, sin in {**_ACENTOS, **{k.upper(): v for k, v in _ACENTOS.items()}}.items():
        expr = func.replace(expr, con, sin)
    for ruido in ("-", " ", "_"):
        expr = func.replace(expr, ruido, "")
    return expr


class RepoCatalogo:
    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def _total(self, consulta: Select) -> int:
        return int(await self.conexion.scalar(select(func.count()).select_from(consulta.subquery())) or 0)

    async def resumen(self) -> dict[str, Any]:
        productos_por_concepto = (
            select(
                PRODUCTO.c.concepto_id.label("cid"),
                func.count(func.distinct(PRODUCTO.c.nivel)).label("niveles"),
            )
            .where(PRODUCTO.c.activo.is_(True))
            .group_by(PRODUCTO.c.concepto_id)
            .subquery()
        )

        fila = (
            await self.conexion.execute(
                select(
                    func.count().label("conceptos"),
                    func.count(productos_por_concepto.c.niveles)
                    .filter(productos_por_concepto.c.niveles >= 3)
                    .label("tres_niveles"),
                    func.count().filter(productos_por_concepto.c.niveles.is_(None)).label("sin_producto"),
                )
                .select_from(
                    CONCEPTO.outerjoin(productos_por_concepto, productos_por_concepto.c.cid == CONCEPTO.c.id)
                )
                .where(CONCEPTO.c.activo.is_(True))
            )
        ).one()

        productos = (
            await self.conexion.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(PRODUCTO.c.imagen_url.is_not(None)).label("con_foto"),
                    func.count().filter(PRODUCTO.c.quality_score < UMBRAL_SIN_REVISAR).label("sin_revisar"),
                ).where(PRODUCTO.c.activo.is_(True))
            )
        ).one()

        tiendas = await self.conexion.scalar(
            select(func.count()).select_from(TIENDA).where(TIENDA.c.activa.is_(True))
        )

        return {
            "conceptos": int(fila.conceptos),
            "productos": int(productos.total),
            "conceptos_con_tres_niveles": int(fila.tres_niveles),
            "conceptos_sin_producto": int(fila.sin_producto),
            "productos_con_foto": int(productos.con_foto),
            "tiendas": int(tiendas or 0),
            "productos_sin_revisar": int(productos.sin_revisar),
        }

    async def categorias(self) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(CONCEPTO.c.categoria, func.count().label("conceptos"))
                .where(CONCEPTO.c.activo.is_(True))
                .group_by(CONCEPTO.c.categoria)
                .order_by(CONCEPTO.c.categoria)
            )
        )

    async def listar_conceptos(
        self,
        *,
        categoria: str | None,
        tipo_item: str | None,
        busqueda: str | None,
        con_producto: bool | None,
        pagina: int,
        por_pagina: int,
    ) -> tuple[int, list[Any]]:
        productos_por_concepto = (
            select(
                PRODUCTO.c.concepto_id.label("cid"),
                func.count().label("productos"),
                func.count(func.distinct(PRODUCTO.c.nivel)).label("niveles"),
            )
            .where(PRODUCTO.c.activo.is_(True))
            .group_by(PRODUCTO.c.concepto_id)
            .subquery()
        )

        consulta = (
            select(
                CONCEPTO.c.codigo,
                CONCEPTO.c.nombre_canonico,
                CONCEPTO.c.categoria,
                CONCEPTO.c.tipo_item,
                CONCEPTO.c.sinonimos,
                CONCEPTO.c.admite_personaje,
                CONCEPTO.c.atributos_discriminantes,
                CONCEPTO.c.atributos_descriptivos,
                CONCEPTO.c.frecuencia_demanda,
                func.coalesce(productos_por_concepto.c.productos, 0).label("productos"),
                func.coalesce(productos_por_concepto.c.niveles, 0).label("niveles"),
            )
            .select_from(
                CONCEPTO.outerjoin(productos_por_concepto, productos_por_concepto.c.cid == CONCEPTO.c.id)
            )
            .where(CONCEPTO.c.activo.is_(True))
        )

        if categoria:
            consulta = consulta.where(CONCEPTO.c.categoria == categoria)
        if tipo_item:
            consulta = consulta.where(CONCEPTO.c.tipo_item == tipo_item)
        if busqueda:
            patron = f"%{busqueda.lower()}%"
            consulta = consulta.where(func.lower(CONCEPTO.c.nombre_canonico).like(patron))
        if con_producto is True:
            consulta = consulta.where(productos_por_concepto.c.productos > 0)
        elif con_producto is False:
            consulta = consulta.where(productos_por_concepto.c.productos.is_(None))

        consulta = consulta.order_by(CONCEPTO.c.frecuencia_demanda.desc(), CONCEPTO.c.codigo)

        total = await self._total(consulta)
        filas = list(await self.conexion.execute(_paginar(consulta, pagina, por_pagina)))
        return total, filas

    async def ver_concepto(self, codigo: str) -> tuple[Any | None, list[Any]]:
        precio_min = _precio_minimo_vigente()
        fila = (
            await self.conexion.execute(select(CONCEPTO).where(CONCEPTO.c.codigo == codigo))
        ).one_or_none()
        if fila is None:
            return None, []
        productos = list(
            await self.conexion.execute(
                _consulta_productos(precio_min)
                .where(PRODUCTO.c.concepto_id == fila.id)
                .order_by(PRODUCTO.c.nivel, PRODUCTO.c.nombre)
            )
        )
        return fila, productos

    async def listar_productos(
        self,
        *,
        concepto: str | None,
        nivel: str | None,
        personaje: str | None,
        con_personaje: bool | None,
        busqueda: str | None,
        con_precio: bool | None,
        con_ofertas: bool,
        pagina: int,
        por_pagina: int,
    ) -> tuple[int, list[Any], dict[Any, list[Any]]]:
        precio_min = _precio_minimo_vigente()
        consulta = _consulta_productos(precio_min)

        if concepto:
            consulta = consulta.where(CONCEPTO.c.codigo == concepto)
        if nivel:
            consulta = consulta.where(PRODUCTO.c.nivel == nivel)
        if personaje:
            clave = _normalizar_personaje(personaje)
            consulta = consulta.where(_normalizado_sql(PRODUCTO.c.personaje) == clave)
        if con_personaje is True:
            consulta = consulta.where(PRODUCTO.c.personaje.is_not(None))
        elif con_personaje is False:
            consulta = consulta.where(PRODUCTO.c.personaje.is_(None))
        if busqueda:
            patron = f"%{busqueda.lower()}%"
            consulta = consulta.where(
                or_(func.lower(PRODUCTO.c.nombre).like(patron), func.lower(PRODUCTO.c.marca).like(patron))
            )
        if con_precio is True:
            consulta = consulta.where(precio_min.c.centavos.is_not(None))

        consulta = consulta.order_by(CONCEPTO.c.codigo, PRODUCTO.c.nivel, PRODUCTO.c.nombre)

        total = await self._total(consulta)
        filas = list(await self.conexion.execute(_paginar(consulta, pagina, por_pagina)))

        ofertas_por_pid: dict[Any, list[Any]] = {}
        if con_ofertas and filas:
            for oferta in await self.conexion.execute(_consulta_ofertas([f.id for f in filas])):
                ofertas_por_pid.setdefault(oferta.pid, []).append(oferta)
        return total, filas, ofertas_por_pid

    async def ver_producto(self, sku: str) -> tuple[Any | None, list[Any]]:
        precio_min = _precio_minimo_vigente()
        fila = (
            await self.conexion.execute(_consulta_productos(precio_min).where(PRODUCTO.c.sku_interno == sku))
        ).one_or_none()
        if fila is None:
            return None, []
        ofertas = list(
            await self.conexion.execute(
                select(
                    TIENDA.c.slug,
                    TIENDA.c.nombre.label("tienda_nombre"),
                    TIENDA.c.tipo,
                    OFERTA.c.url,
                    OFERTA.c.disponible,
                    OFERTA.c.metodo_vinculacion,
                    OFERTA.c.confianza_vinculacion,
                    PRECIO.c.valor_centavos,
                    PRECIO.c.vigente_desde,
                    PRECIO.c.vigente_hasta,
                    PRECIO.c.fuente,
                )
                .select_from(
                    OFERTA.join(TIENDA, TIENDA.c.id == OFERTA.c.tienda_id).outerjoin(
                        PRECIO,
                        and_(PRECIO.c.oferta_id == OFERTA.c.id, PRECIO.c.vigente_hasta.is_(None)),
                    )
                )
                .where(OFERTA.c.producto_canonico_id == fila.id, OFERTA.c.activo.is_(True))
            )
        )
        return fila, ofertas

    async def producto_por_sku(self, sku: str) -> Any | None:
        precio_min = _precio_minimo_vigente()
        return (
            await self.conexion.execute(_consulta_productos(precio_min).where(PRODUCTO.c.sku_interno == sku))
        ).one_or_none()

    async def existe_producto(self, sku: str) -> Any | None:
        return await self.conexion.scalar(select(PRODUCTO.c.id).where(PRODUCTO.c.sku_interno == sku))

    async def actualizar_producto(self, sku: str, valores: dict[str, Any]) -> None:
        if valores:
            await self.conexion.execute(
                update(PRODUCTO).where(PRODUCTO.c.sku_interno == sku).values(**valores)
            )

    async def concepto_id_por_codigo(self, codigo: Any) -> Any | None:
        return await self.conexion.scalar(select(CONCEPTO.c.id).where(CONCEPTO.c.codigo == codigo))

    async def reclasificar_producto(self, sku: str, concepto_id: Any, codigo: str) -> str:
        nuevo_sku = await self.sku_reacunado(sku, codigo)
        await self.conexion.execute(
            update(PRODUCTO)
            .where(PRODUCTO.c.sku_interno == sku)
            .values(concepto_id=concepto_id, texto_embedding=None, sku_interno=nuevo_sku)
        )
        return nuevo_sku

    async def sku_reacunado(self, sku: str, codigo: str) -> str:
        partes = sku.split("-")
        if (
            len(partes) < 3
            or partes[0] != "TK"
            or not re.fullmatch(r"C\d{3}", partes[1])
            or partes[1] == codigo
        ):
            return sku
        base = "-".join([partes[0], codigo, *partes[2:]])
        candidato, n = base, 2
        while await self.conexion.scalar(select(PRODUCTO.c.id).where(PRODUCTO.c.sku_interno == candidato)):
            candidato, n = f"{base}-{n}", n + 1
        return candidato

    async def retirar_producto(self, sku: str) -> None:
        await self.conexion.execute(
            update(PRODUCTO).where(PRODUCTO.c.sku_interno == sku).values(activo=False)
        )

    async def listar_personajes(self) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(
                    PRODUCTO.c.personaje,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    func.count().label("productos"),
                )
                .select_from(PRODUCTO.join(CONCEPTO, CONCEPTO.c.id == PRODUCTO.c.concepto_id))
                .where(PRODUCTO.c.activo.is_(True), PRODUCTO.c.personaje.is_not(None))
                .group_by(PRODUCTO.c.personaje, CONCEPTO.c.codigo)
            )
        )

    async def listar_tiendas(self) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(
                    TIENDA.c.slug,
                    TIENDA.c.nombre,
                    TIENDA.c.tipo,
                    TIENDA.c.url_base,
                    func.count(OFERTA.c.id).label("ofertas"),
                )
                .select_from(
                    TIENDA.outerjoin(
                        OFERTA, and_(OFERTA.c.tienda_id == TIENDA.c.id, OFERTA.c.activo.is_(True))
                    )
                )
                .where(TIENDA.c.activa.is_(True))
                .group_by(TIENDA.c.slug, TIENDA.c.nombre, TIENDA.c.tipo, TIENDA.c.url_base)
                .order_by(func.count(OFERTA.c.id).desc(), TIENDA.c.slug)
            )
        )

    async def listar_listas(
        self,
        *,
        colegio_id: uuid.UUID | None,
        grado: str | None,
        anio_lectivo: int | None,
        revisada: bool | None,
        pagina: int,
        por_pagina: int,
    ) -> tuple[int, list[Any]]:
        items_por_version = (
            select(ITEM.c.version_id.label("vid"), func.count().label("renglones"))
            .group_by(ITEM.c.version_id)
            .subquery()
        )

        consulta = (
            select(
                LISTA.c.id,
                LISTA.c.colegio_id,
                LISTA.c.sede_id,
                LISTA.c.grado,
                LISTA.c.anio_lectivo,
                VERSION.c.id.label("version_id"),
                VERSION.c.numero,
                VERSION.c.publicada_en,
                VERSION.c.revisada_en,
                func.coalesce(items_por_version.c.renglones, 0).label("renglones"),
            )
            .select_from(
                LISTA.join(
                    VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.vigente.is_(True))
                ).outerjoin(items_por_version, items_por_version.c.vid == VERSION.c.id)
            )
            .where(LISTA.c.activa.is_(True))
        )

        if colegio_id is not None:
            consulta = consulta.where(LISTA.c.colegio_id == colegio_id)
        if grado:
            consulta = consulta.where(LISTA.c.grado == grado)
        if anio_lectivo is not None:
            consulta = consulta.where(LISTA.c.anio_lectivo == anio_lectivo)
        if revisada is True:
            consulta = consulta.where(VERSION.c.revisada_en.is_not(None))
        elif revisada is False:
            consulta = consulta.where(VERSION.c.revisada_en.is_(None))

        consulta = consulta.order_by(LISTA.c.anio_lectivo.desc(), LISTA.c.colegio_id, LISTA.c.grado)

        total = await self._total(consulta)
        filas = list(await self.conexion.execute(_paginar(consulta, pagina, por_pagina)))
        return total, filas

    async def ver_lista(self, lista_id: uuid.UUID) -> tuple[Any | None, list[Any]]:
        cabeza = (
            await self.conexion.execute(
                select(LISTA, VERSION.c.id.label("version_id"), VERSION.c.numero, VERSION.c.revisada_en)
                .select_from(
                    LISTA.join(VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.vigente.is_(True)))
                )
                .where(LISTA.c.id == lista_id)
            )
        ).one_or_none()
        if cabeza is None:
            return None, []
        filas = list(
            await self.conexion.execute(
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
                    CONCEPTO.c.tipo_item.label("concepto_tipo_item"),
                )
                .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
                .where(ITEM.c.version_id == cabeza.version_id)
                .order_by(ITEM.c.orden)
            )
        )
        return cabeza, filas

    async def retirar_de_contacto(
        self, contacto_referencia: uuid.UUID, tarea_id: uuid.UUID | None, version_id: uuid.UUID | None
    ) -> int:
        if version_id is None and tarea_id is not None:
            fila = (
                await self.conexion.execute(
                    select(TAREA.c.id, TAREA.c.version_id).where(
                        TAREA.c.id == tarea_id, TAREA.c.contacto_referencia == contacto_referencia
                    )
                )
            ).one_or_none()
            if fila is None:
                return 0
            version_id = fila.version_id
        if version_id is not None:
            filtro = TAREA.c.version_id == version_id
        elif tarea_id is not None:
            filtro = TAREA.c.id == tarea_id
        else:
            return 0
        resultado = await self.conexion.execute(
            update(TAREA)
            .where(filtro, TAREA.c.contacto_referencia == contacto_referencia)
            .values(contacto_referencia=None, retirada_en=datetime.now(UTC))
        )
        return int(resultado.rowcount or 0)

    async def tareas_por_contacto(self, contacto_referencia: uuid.UUID) -> list[Any]:
        consulta = (
            select(
                TAREA.c.id,
                TAREA.c.version_id,
                TAREA.c.colegio_id,
                TAREA.c.grado,
                TAREA.c.anio_lectivo,
                TAREA.c.colegio_datos,
                TAREA.c.creada_en,
                VERSION.c.revisada_en,
            )
            .select_from(TAREA.outerjoin(VERSION, VERSION.c.id == TAREA.c.version_id))
            .where(TAREA.c.contacto_referencia == contacto_referencia)
            .order_by(TAREA.c.creada_en.desc())
        )
        return list(await self.conexion.execute(consulta))
