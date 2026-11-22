"""Versiones de los kits canonicos (editar es copiar) y consultas por colegio y acudiente."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert, select, update
from tukit_comun.cifrado import cifrador_desde_entorno

from ..modelos import (
    EstadoTrabajo,
)
from ..repositorios.trabajos import TrabajoNoExiste
from .base import (
    CANDIDATO,
    ETAPA,
    ITEM,
    KIT,
    KIT_CANONICO,
    LINEA,
    ORIGEN_CANONICO,
    RESOLUCION,
    TRABAJO,
    BorradorDesactualizado,
)
from .formas import _identidad_de_grado, _linea_publica, _objetivos_de_lineas, _sin_apodo


async def _basado_en(conexion: Any, trabajo_id: uuid.UUID) -> uuid.UUID | None:
    """El canonico del que se copio este borrador, o None si no es un borrador."""
    hijos = await conexion.scalar(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    origen = next(iter(hijos or ()), {}).get("basado_en")
    return uuid.UUID(str(origen)) if origen else None


async def _canonico_vigente_de(conexion: Any, trabajo_id: uuid.UUID) -> uuid.UUID | None:
    """El trabajo al que apunta hoy la cache del (colegio, grado, anio) de este."""
    hijos = await conexion.scalar(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    identidad = _identidad_de_grado(hijos)
    if identidad is None:
        return None
    colegio_id, grado, anio, _ = identidad
    return await conexion.scalar(
        select(KIT_CANONICO.c.trabajo_id).where(
            KIT_CANONICO.c.colegio_id == colegio_id,
            KIT_CANONICO.c.grado == grado,
            KIT_CANONICO.c.anio_lectivo == anio,
        )
    )


async def _borrador_abierto(conexion: Any, canonico_id: uuid.UUID) -> uuid.UUID | None:
    """El borrador sin publicar que ya salio de este canonico, si hay uno.

    `basado_en` vive en el JSON `hijos`, no en una columna: se filtra en memoria
    sobre los pocos `canonico_lista` en revision (los del poller se publican
    solos y nunca quedan aqui).
    """
    filas = await conexion.execute(
        select(TRABAJO.c.id, TRABAJO.c.hijos)
        .where(
            TRABAJO.c.origen == ORIGEN_CANONICO,
            TRABAJO.c.estado == EstadoTrabajo.ESPERA_REVISION.value,
        )
        .order_by(TRABAJO.c.creado_en)
    )
    for fila in filas:
        if str(next(iter(fila.hijos or ()), {}).get("basado_en")) == str(canonico_id):
            return fila.id
    return None


async def _copiar_filas(
    conexion: Any, tabla: Any, filas: list[Any], **remapeos: dict[Any, Any]
) -> dict[Any, Any]:
    """Inserta copias de `filas` con id nuevo; `remapeos` traduce sus FKs.

    Devuelve {id viejo: id nuevo} para que la tabla hija remapee las suyas.
    """
    nuevos: dict[Any, Any] = {}
    for fila in filas:
        valores = dict(fila._mapping)
        nuevos[valores["id"]] = valores["id"] = uuid.uuid4()
        for columna, mapa in remapeos.items():
            if valores.get(columna) is not None:
                valores[columna] = mapa[valores[columna]]
        await conexion.execute(insert(tabla).values(**valores))
    return nuevos


async def abrir_borrador(motor: Any, canonico_id: uuid.UUID) -> dict[str, Any]:
    """Una copia editable de los kits canonicos vigentes de un grado.

    Los kits publicados no se editan en sitio: el acudiente que ya empezo
    apunta a ese trabajo (`hijos[0].canonico_trabajo_id`) y debe seguir viendo
    lo que pago. Se copia el trabajo entero —items, candidatos, resoluciones,
    kits y lineas, con ids nuevos— a un `canonico_lista` en `espera_revision`
    que la consola de siempre corrige, y `fijar_como_canonico` lo publica como
    la version nueva. El historial de transiciones no se copia: es del original.

    Idempotente: si el canonico ya tiene un borrador abierto, devuelve ese.
    """
    async with motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == canonico_id))).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(str(canonico_id))
        # Cualquier canonico vigente, aunque haya salido del trabajo aprobado de
        # un acudiente: la copia no lleva su usuario ni sus preferencias.
        if await _canonico_vigente_de(conexion, canonico_id) != canonico_id:
            raise BorradorDesactualizado()
        abierto = await _borrador_abierto(conexion, canonico_id)
        if abierto is not None:
            return {"trabajo_id": str(abierto), "basado_en": str(canonico_id), "nuevo": False}

        borrador_id = uuid.uuid4()
        # Sin apodo: el borrador es de la consola, no de un acudiente.
        hijos = [_sin_apodo(dict(h)) for h in fila.hijos or ()]
        hijos[0]["basado_en"] = str(canonico_id)
        await conexion.execute(
            insert(TRABAJO).values(
                id=borrador_id,
                usuario_id=None,
                estado=EstadoTrabajo.ESPERA_REVISION.value,
                origen=ORIGEN_CANONICO,
                hijos=hijos,
                estimado_segundos=fila.estimado_segundos,
                degradaciones=list(fila.degradaciones or ()),
            )
        )
        etapas = list(await conexion.execute(select(ETAPA).where(ETAPA.c.trabajo_id == canonico_id)))
        await _copiar_filas(conexion, ETAPA, etapas, trabajo_id={canonico_id: borrador_id})
        items = list(await conexion.execute(select(ITEM).where(ITEM.c.trabajo_id == canonico_id)))
        mapa_items = await _copiar_filas(conexion, ITEM, items, trabajo_id={canonico_id: borrador_id})
        de_items = list(mapa_items)
        candidatos = list(
            await conexion.execute(select(CANDIDATO).where(CANDIDATO.c.item_crudo_id.in_(de_items)))
        )
        mapa_candidatos = await _copiar_filas(conexion, CANDIDATO, candidatos, item_crudo_id=mapa_items)
        resoluciones = list(
            await conexion.execute(select(RESOLUCION).where(RESOLUCION.c.item_crudo_id.in_(de_items)))
        )
        await _copiar_filas(
            conexion,
            RESOLUCION,
            resoluciones,
            item_crudo_id=mapa_items,
            candidato_item_id=mapa_candidatos,
        )
        kits = list(await conexion.execute(select(KIT).where(KIT.c.trabajo_id == canonico_id)))
        mapa_kits = await _copiar_filas(conexion, KIT, kits, trabajo_id={canonico_id: borrador_id})
        lineas = list(await conexion.execute(select(LINEA).where(LINEA.c.kit_id.in_(list(mapa_kits)))))
        await _copiar_filas(conexion, LINEA, lineas, kit_id=mapa_kits, item_crudo_id=mapa_items)
    return {"trabajo_id": str(borrador_id), "basado_en": str(canonico_id), "nuevo": True}


async def _recalcular_objetivos(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Pone al dia costo, fidelidad y disponibilidad de cada kit del trabajo.

    Misma regla que el kit aplicado de la ruta rapida (`_objetivos_de_lineas`);
    las demas llaves del armado (p. ej. `resolucion_auto`) se conservan.
    """
    for kit in list(await conexion.execute(select(KIT).where(KIT.c.trabajo_id == trabajo_id))):
        lineas = [
            _linea_publica(f) for f in await conexion.execute(select(LINEA).where(LINEA.c.kit_id == kit.id))
        ]
        total = sum(int(linea["subtotal_linea"] or 0) for linea in lineas)
        objetivos = {**(kit.objetivos or {}), **_objetivos_de_lineas(lineas, total)}
        await conexion.execute(
            update(KIT).where(KIT.c.id == kit.id).values(objetivos=objetivos, total_cop=total)
        )


async def grados_canonicos(motor: Any, *, colegio_id: str | None = None) -> list[dict[str, Any]]:
    """Los (colegio, grado, anio) que ya tienen cache bendita, para el selector.

    Es lo que `/empezar` lista en vez de pedir un PDF: un grado que aparece aqui
    se puede aplicar al vuelo (ruta rapida); uno que no, entra al pipeline.
    """
    consulta = (
        select(
            KIT_CANONICO.c.colegio_id,
            KIT_CANONICO.c.grado,
            KIT_CANONICO.c.anio_lectivo,
            KIT_CANONICO.c.trabajo_id,
            TRABAJO.c.terminado_en,
        )
        .select_from(KIT_CANONICO.join(TRABAJO, TRABAJO.c.id == KIT_CANONICO.c.trabajo_id))
        .order_by(KIT_CANONICO.c.colegio_id, KIT_CANONICO.c.grado)
    )
    if colegio_id:
        consulta = consulta.where(KIT_CANONICO.c.colegio_id == colegio_id)
    async with motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))
        # Solo el admin de un colegio pregunta por su borrador; el selector de
        # /empezar (sin colegio) no paga esa consulta.
        borradores = (
            {f.trabajo_id: await _borrador_abierto(conexion, f.trabajo_id) for f in filas}
            if colegio_id
            else {}
        )
    return [
        {
            "colegio_id": f.colegio_id,
            "grado": f.grado,
            "anio_lectivo": int(f.anio_lectivo),
            "trabajo_id": str(f.trabajo_id),
            "publicado_en": f.terminado_en.isoformat() if f.terminado_en else None,
            "borrador_trabajo_id": (str(borradores[f.trabajo_id]) if borradores.get(f.trabajo_id) else None),
        }
        for f in filas
    ]


async def acudientes_de_colegio(motor: Any, *, colegio_id: str) -> list[dict[str, Any]]:
    """Los acudientes de un colegio con el estado de su trabajo más reciente.

    Agrupa por `usuario_id` (el identificador del acudiente, jamás su correo ni
    el nombre de un menor) y se queda con el trabajo VIVO: el más nuevo de cada
    acudiente. El colegio no es columna del trabajo —vive en el JSON `hijos`—,
    así que el filtro es por ese campo. Los trabajos anónimos (sin `usuario_id`)
    no se agrupan: no hay a quién listar.

    Devuelve además los `grados` que ese acudiente pidió EN ESTE colegio (de los
    hijos que le corresponden) y las `preferencias` del hogar descifradas —pesos,
    presupuesto, personaje—: dato de negocio, no PII (no lleva correo ni el
    nombre del menor), y es lo que el panel necesita para atenderlo sin abrir el
    trabajo.
    """
    cifrador = cifrador_desde_entorno()
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.usuario_id,
            TRABAJO.c.estado,
            TRABAJO.c.actualizado_en,
            TRABAJO.c.hijos,
            TRABAJO.c.preferencias_cifradas,
        )
        .where(TRABAJO.c.usuario_id.is_not(None))
        .order_by(TRABAJO.c.usuario_id, TRABAJO.c.actualizado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = (await conexion.execute(consulta)).all()

    # ponytail: filtro por colegio en Python sobre los trabajos recientes — un
    # colegio tiene decenas de acudientes, no hace falta índice sobre el JSON.
    # Subir a JSON containment (`hijos @> …`) si un colegio pasa de miles.
    ultimos: dict[str, Any] = {}
    for f in filas:  # ya vienen por usuario, más reciente primero
        if any(h.get("colegio_id") == colegio_id for h in (f.hijos or ())):
            ultimos.setdefault(str(f.usuario_id), f)

    def _grados_en_colegio(f: Any) -> list[str]:
        # Solo los grados de los hijos de ESTE colegio, sin repetir. Un hogar
        # tiene uno o dos: orden alfabético basta, no vale un índice canónico.
        grados = {h["grado"] for h in (f.hijos or ()) if h.get("colegio_id") == colegio_id and h.get("grado")}
        return sorted(grados)

    return [
        {
            "usuario_id": uid,
            "estado": f.estado,
            "actualizado_en": f.actualizado_en.isoformat() if f.actualizado_en else None,
            "trabajo_id": str(f.id),
            "grados": _grados_en_colegio(f),
            "preferencias": cifrador.descifrar_json(f.preferencias_cifradas) or {}
            if f.preferencias_cifradas
            else {},
        }
        for uid, f in ultimos.items()
    ]


async def mis_trabajos(motor: Any, *, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    """Los trabajos (solicitudes de kit) de UN acudiente, del mas nuevo al mas viejo.

    Es la lectura del panel del acudiente: sus solicitudes de kit —lo que
    `/empezar` crea—, que no son pedidos pagados (esos los sirve comercio) sino
    trabajos del pipeline. Devuelve por cada uno el estado, los hijos (por
    `referencia`/`colegio_id`/`grado`, jamas un nombre de menor) y las
    preferencias del hogar descifradas, que son del titular y las pidio el.
    """
    cifrador = cifrador_desde_entorno()
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.hijos,
            TRABAJO.c.preferencias_cifradas,
            TRABAJO.c.creado_en,
        )
        .where(TRABAJO.c.usuario_id == usuario_id)
        .order_by(TRABAJO.c.creado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = (await conexion.execute(consulta)).all()

    return [
        {
            "trabajo_id": str(f.id),
            "estado": f.estado,
            "creado_en": f.creado_en.isoformat() if f.creado_en else None,
            "hijos": list(f.hijos or ()),
            "preferencias": cifrador.descifrar_json(f.preferencias_cifradas) or {}
            if f.preferencias_cifradas
            else {},
        }
        for f in filas
    ]
