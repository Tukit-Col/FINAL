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

    def __init__(self, conexion: Any) -> None:
        self.c = conexion

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
        actual = await self.estado(trabajo_id)
        if actual == nuevo:
            return
        if not puede_pasar(actual, nuevo):
            raise TransicionIlegal(actual, nuevo)
        await self.c.execute(update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(estado=nuevo, **extra))

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

    async def resolucion_de(self, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> Any:
        return (
            await self.c.execute(
                select(RESOLUCION)
                .select_from(RESOLUCION.join(ITEM, ITEM.c.id == RESOLUCION.c.item_crudo_id))
                .where(ITEM.c.trabajo_id == trabajo_id, ITEM.c.id == item_id)
            )
        ).one_or_none()

    async def emitir_evento(self, trabajo_id: uuid.UUID) -> None:
        fila = (
            await self.c.execute(
                select(TRABAJO.c.usuario_id, TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id)
            )
        ).one_or_none()
        usuario_id = fila.usuario_id if fila is not None else None
        carga: dict[str, Any] = {"trabajo_id": str(trabajo_id), "publicado_en": _ahora().isoformat()}
        if usuario_id is not None:
            carga["usuario_id"] = str(usuario_id)
        hijos = [h for h in (fila.hijos or ()) if isinstance(h, dict)] if fila is not None else []
        con_lineas = {
            ref
            for ref in (
                await self.c.execute(
                    select(LINEA.c.hijo_referencia)
                    .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
                    .where(KIT.c.trabajo_id == trabajo_id)
                    .distinct()
                )
            ).scalars()
        }
        if con_lineas:
            hijos = [h for h in hijos if str(h.get("referencia")) in con_lineas] or hijos
        if hijos:
            if hijos[0].get("colegio_id"):
                carga["colegio_id"] = str(hijos[0]["colegio_id"])
            if hijos[0].get("grado"):
                carga["grado"] = str(hijos[0]["grado"])
        listas: list[dict[str, str]] = []
        for hijo in hijos:
            lista = {"colegio_id": str(hijo.get("colegio_id") or ""), "grado": str(hijo.get("grado") or "")}
            if (lista["colegio_id"] or lista["grado"]) and lista not in listas:
                listas.append(lista)
        if listas:
            carga["listas"] = listas
        await self.c.execute(
            insert(BANDEJA).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=trabajo_id,
                carga=con_correlacion(carga),
            )
        )

    async def avisar_encolado(self, trabajo_id: uuid.UUID) -> None:
        await self.c.execute(
            insert(BANDEJA).values(
                tipo="trabajo_encolado",
                agregado_tipo="trabajo_pipeline",
                agregado_id=trabajo_id,
                carga=con_correlacion({"trabajo_id": str(trabajo_id)}),
            )
        )

    async def fijar_canonico(self, trabajo_id: uuid.UUID) -> None:
        fila = (await self.c.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        hijos = list(fila.hijos or ()) if fila else []
        if len(hijos) != 1:
            return
        hijo = hijos[0]
        colegio_id = str(hijo.get("colegio_id") or "")
        grado = str(hijo.get("grado") or "")
        anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
        if not (colegio_id and grado):
            return

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
