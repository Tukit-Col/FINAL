"""El SQL por-transaccion del pipeline de trabajos (ADR 0019).

`RepoTrabajos` se ata a una conexion en `__init__` y expone un metodo por
consulta, con el SQL verbatim que vivia en `trabajos.py`. No abre ni cierra la
transaccion ni traduce excepciones: eso queda en el orquestador (`trabajos.py`),
que es quien decide los limites de cada `async with` —en particular el que
mantiene `emitir_evento` (outbox) y el cambio de estado que lo dispara en una
SOLA transaccion, para que un evento no sobreviva a un rollback (no dual-write)—.

El guard de la maquina de estados (`puede_pasar`) SI vive dentro de `pasar_a`:
es una invariante transaccional, no una regla de presentacion, y el repo es
quien escribe el cambio que la puede violar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from tukit_comun.bandeja import con_correlacion

from ..dominio.maquina import puede_pasar
from ..modelos import PESOS_POR_OMISION, Base

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
ETAPA = Base.metadata.tables["etapa_trabajo"]
ITEM = Base.metadata.tables["item_crudo"]
CANDIDATO = Base.metadata.tables["candidato_item"]
RESOLUCION = Base.metadata.tables["resolucion_item"]
TRANSICION = Base.metadata.tables["transicion_resolucion"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
KIT_CANONICO = Base.metadata.tables["kit_canonico"]

ANIO_LECTIVO_POR_OMISION = 2026


class TrabajoNoExiste(Exception):
    pass


class TransicionIlegal(Exception):
    def __init__(self, actual: str, pedida: str) -> None:
        super().__init__(f"no se puede pasar de {actual} a {pedida}")
        self.actual = actual
        self.pedida = pedida


def _ahora() -> datetime:
    return datetime.now(UTC)


class RepoTrabajos:
    """Las consultas del pipeline, atadas a una conexion abierta por el orquestador."""

    def __init__(self, conexion: Any) -> None:
        self.c = conexion

    # --- etapas y estado ---------------------------------------------------

    async def marcar_etapa(
        self,
        trabajo_id: uuid.UUID,
        nombre: str,
        estado: str,
        *,
        ms: int | None = None,
        detalle: dict[str, Any] | None = None,
    ) -> None:
        await self.c.execute(
            update(ETAPA)
            .where(ETAPA.c.trabajo_id == trabajo_id, ETAPA.c.nombre == nombre)
            .values(estado=estado, ms=ms, detalle=detalle or {}, terminada_en=_ahora())
        )

    async def estado(self, trabajo_id: uuid.UUID) -> str:
        valor = await self.c.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
        if valor is None:
            raise TrabajoNoExiste(str(trabajo_id))
        return str(valor)

    async def pasar_a(self, trabajo_id: uuid.UUID, nuevo: str, **extra: Any) -> None:
        # El guard vive aqui, junto a la escritura que puede violar la maquina:
        # es una invariante transaccional, no una regla de presentacion.
        actual = await self.estado(trabajo_id)
        if actual == nuevo:
            return
        if not puede_pasar(actual, nuevo):
            raise TransicionIlegal(actual, nuevo)
        await self.c.execute(update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(estado=nuevo, **extra))

    # --- escritura de kits -------------------------------------------------

    async def escribir_kits(
        self,
        trabajo_id: uuid.UUID,
        kits: list[Any],
        ids_item: dict[tuple[str, int], uuid.UUID],
        preferencias: dict[str, Any],
        cifrador: Any,
        *,
        ms: int,
    ) -> None:
        """Persiste KIT+LINEA y marca la etapa de optimizacion. Comun a las dos rutas."""
        for kit in kits:
            kit_id = uuid.uuid4()
            await self.c.execute(
                insert(KIT).values(
                    id=kit_id,
                    trabajo_id=trabajo_id,
                    perfil=kit.perfil,
                    total_cop=kit.total_cop,
                    objetivos=kit.objetivos,
                    recomendado=kit.recomendado,
                    razon_recomendacion=kit.razon,
                    dentro_de_presupuesto=kit.dentro_de_presupuesto,
                    pesos_usados_cifrados=cifrador.cifrar_json(
                        {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
                    ),
                    consolidaciones=list(kit.consolidaciones),
                )
            )
            for linea in kit.lineas:
                elegido = linea.elegido
                await self.c.execute(
                    insert(LINEA).values(
                        id=uuid.uuid4(),
                        kit_id=kit_id,
                        item_crudo_id=ids_item[(linea.hijo, linea.orden)],
                        producto_canonico_id=(
                            uuid.UUID(elegido.producto_id) if elegido and elegido.producto_id else None
                        ),
                        hijo_referencia=linea.hijo,
                        orden=linea.orden,
                        descripcion=linea.descripcion,
                        tipo=linea.tipo,
                        estado_resolucion=linea.estado_resolucion,
                        cantidad_pedida=linea.cantidad_pedida,
                        unidad_base=linea.unidad_base,
                        unidades_por_empaque=linea.unidades_por_empaque,
                        unidades_a_comprar=linea.unidades_a_comprar,
                        sku=elegido.sku if elegido else None,
                        nombre_producto=elegido.nombre if elegido else None,
                        marca=elegido.marca if elegido else None,
                        nivel=elegido.nivel if elegido else None,
                        personaje=elegido.personaje if elegido else None,
                        imagen_url=elegido.imagen_url if elegido else None,
                        confianza=None,
                        precio_unitario_cop=linea.precio_unitario_cop,
                        subtotal_cop=linea.subtotal_cop,
                        informativa=linea.informativa,
                        instruccion_colegio=linea.instruccion_colegio,
                        url_externa=linea.url_externa,
                        mensaje=linea.mensaje,
                        no_consolidable=linea.no_consolidable,
                        motivo_no_consolidable=linea.motivo_no_consolidable,
                        alternativas=[
                            {
                                "sku": alternativa.sku,
                                "nombre": alternativa.nombre,
                                "nivel": alternativa.nivel,
                                "precio_cop": alternativa.precio_cop,
                                "imagen_url": alternativa.imagen_url,
                            }
                            for alternativa in linea.alternativas
                        ],
                    )
                )

        await self.marcar_etapa(
            trabajo_id,
            "optimizacion",
            "ok",
            ms=ms,
            detalle={
                "kits": len(kits),
                "recomendado": next((k.perfil for k in kits if k.recomendado), None),
            },
        )

    async def recalcular_total_kit(self, kit_id: uuid.UUID) -> None:
        total = await self.c.scalar(
            select(func.coalesce(func.sum(LINEA.c.subtotal_cop), 0)).where(LINEA.c.kit_id == kit_id)
        )
        await self.c.execute(update(KIT).where(KIT.c.id == kit_id).values(total_cop=int(total or 0)))

    # --- resolucion --------------------------------------------------------

    async def resolucion_de(self, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(RESOLUCION)
                .select_from(RESOLUCION.join(ITEM, ITEM.c.id == RESOLUCION.c.item_crudo_id))
                .where(ITEM.c.trabajo_id == trabajo_id, ITEM.c.id == item_id)
            )
        ).one_or_none()

    # --- outbox: MISMA transaccion que el cambio de estado ----------------

    async def emitir_evento(self, trabajo_id: uuid.UUID) -> None:
        """Deja `kits_publicados` en la bandeja, en la MISMA transaccion.

        El repartidor de Operacion (`tukit_operacion.repartidor`) lo drena y avisa
        al acudiente resolviendo su `usuario_id` desde `trabajo_pipeline`. Por eso
        este evento solo tiene sentido en un trabajo con acudiente; un preview
        (`usuario_id` NULL) no llega aca —`revisar` lo rechaza antes— para no dejar
        un evento sin destinatario que el repartidor reintente sin fin. Por la
        misma razon `promover_vista_previa` publica el preview sin emitir, y
        `trabajos._publicar_evento` no llama aqui si el trabajo no tiene acudiente.

        No abre transaccion: el orquestador lo llama dentro del mismo `async with`
        que el paso a PUBLICADO, de modo que un rollback a mitad se lleva el evento
        con el cambio de estado (no dual-write).
        """
        await self.c.execute(
            insert(BANDEJA).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=trabajo_id,
                carga=con_correlacion({"trabajo_id": str(trabajo_id), "publicado_en": _ahora().isoformat()}),
            )
        )

    # --- cache canonica del grado -----------------------------------------

    async def fijar_canonico(self, trabajo_id: uuid.UUID) -> None:
        """Al publicar, apunta la cache canonica de (colegio, grado, anio) a este trabajo.

        Solo cuando el trabajo tiene UNA identidad de grado clara: un solo hijo con
        colegio y grado (el caso de onboarding y de la ruta de acudiente por grado).
        Un trabajo multi-hogar, o sin colegio/grado, no define una cache de grado y
        se deja sin puntero —publicar igual funciona, solo no se cachea—.

        Publicar de nuevo para el mismo grado REEMPLAZA el puntero (delete + insert
        sobre la llave unica): una sola cache bendita por grado.
        """
        fila = (await self.c.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        hijos = list(fila.hijos or ()) if fila else []
        if len(hijos) != 1:
            return
        hijo = hijos[0]
        colegio_id = str(hijo.get("colegio_id") or "")
        grado = str(hijo.get("grado") or "")
        # Mismo anio bajo el que se construyeron los kits (ver `procesar`): si el
        # hijo no lo trajo, se cachea bajo el de omision para que la busqueda por
        # grado en /empezar caiga en la misma fila.
        anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
        if not (colegio_id and grado):
            return

        # Reemplaza el puntero del grado: la cache es una sola. No es un upsert de
        # ON CONFLICT para no atarse al dialecto —delete+insert corre igual en
        # SQLite (pruebas) y en Postgres (real)—.
        await self.c.execute(
            delete(KIT_CANONICO).where(
                KIT_CANONICO.c.colegio_id == colegio_id,
                KIT_CANONICO.c.grado == grado,
                KIT_CANONICO.c.anio_lectivo == anio,
            )
        )
        await self.c.execute(
            insert(KIT_CANONICO).values(
                id=uuid.uuid4(),
                colegio_id=colegio_id,
                grado=grado,
                anio_lectivo=anio,
                trabajo_id=trabajo_id,
            )
        )
