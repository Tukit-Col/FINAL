from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, insert, select, update
from tukit_comun.bandeja import con_correlacion
from tukit_comun.http import iso as _iso

from ..dominio.alertas import ALERTAS, alertas_de_pedido
from ..dominio.ley1480 import evaluar_devolucion
from ..dominio.linea_de_tiempo import AvanceVisto, EnvioVisto, PagoVisto
from ..dominio.pagos import CAMPOS_FIRMA_ENTREGA, ESTADOS_PAGO_FINALES, pedido_tras_pago
from ..modelos import Base, EstadoPago, EstadoPedido, transicion_valida
from ..pasarela import EventoPasarela

PEDIDO = Base.metadata.tables["pedido"]
LINEA_PEDIDO = Base.metadata.tables["linea_pedido"]
PAGO = Base.metadata.tables["pago"]
ENVIO = Base.metadata.tables["envio"]
DEVOLUCION = Base.metadata.tables["devolucion"]
RESERVA = Base.metadata.tables["reserva_inventario"]
EVENTO_PROCESADO = Base.metadata.tables["evento_pasarela_procesado"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
HISTORIAL = Base.metadata.tables["historial_pedido"]

_ESTADOS_CONFIRMADOS = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
        EstadoPedido.ENTREGADO.value,
    }
)

_ESTADOS_ENTREGA_PENDIENTE = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
    }
)


def _serializar_pago(fila: Any) -> dict[str, Any] | None:
    if fila is None:
        return None
    return {
        "referencia_wompi": fila.referencia_wompi,
        "metodo": fila.metodo,
        "estado": fila.estado,
        "monto": int(fila.monto),
    }


def _serializar_envio(fila: Any, *, con_celular: bool = False) -> dict[str, Any] | None:
    if fila is None:
        return None
    envio = {
        "destinatario": fila.destinatario,
        "direccion": fila.direccion,
        "ciudad": fila.ciudad,
        "telefono": fila.telefono,
        "departamento": fila.departamento,
        "documento_destinatario": fila.documento_destinatario,
        "indicaciones": fila.indicaciones,
        "localidad": fila.localidad,
        "latitud": fila.latitud,
        "longitud": fila.longitud,
        "transportadora": fila.transportadora,
        "guia": fila.guia,
        "repartidor_nombre": fila.repartidor_nombre,
        "entrega_estimada": _iso(fila.entrega_estimada),
        "entregado_en": _iso(fila.entregado_en),
    }
    if con_celular:
        envio["repartidor_celular"] = fila.repartidor_celular
    return envio


def _serializar_historial(fila: Any) -> dict[str, Any]:
    return {
        "estado_desde": fila.estado_desde,
        "estado_hacia": fila.estado_hacia,
        "actor_id": str(fila.actor_id),
        "actor_correo": fila.actor_correo,
        "nota": fila.nota,
        "tipo_incidencia": fila.tipo_incidencia,
        "creado_en": _iso(fila.creado_en),
    }


def _serializar_linea(fila: Any) -> dict[str, Any]:
    return {
        "sku": fila.sku,
        "nombre": fila.nombre,
        "cantidad": int(fila.cantidad),
        "precio_unitario": int(fila.precio_unitario),
    }


@dataclass(frozen=True)
class ResultadoAplicacion:

    estado: str
    pedido_id: uuid.UUID | None
    estado_pago: str | None
    estado_pedido: str | None
    transicionado: bool
    pagado: bool = False


class RepoPedidos:

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def pedido_completo(self, fila_pedido: Any, *, con_celular: bool = False) -> dict[str, Any]:
        lineas = [
            _serializar_linea(f)
            for f in await self.conexion.execute(
                select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id == fila_pedido.id)
            )
        ]
        pago = (
            await self.conexion.execute(
                select(PAGO)
                .where(PAGO.c.pedido_id == fila_pedido.id)
                .order_by(PAGO.c.creado_en.desc())
                .limit(1)
            )
        ).one_or_none()
        envio = (
            await self.conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == fila_pedido.id))
        ).one_or_none()

        return {
            "pedido_id": str(fila_pedido.id),
            "usuario_id": str(fila_pedido.usuario_id),
            "trabajo_id": str(fila_pedido.trabajo_id) if fila_pedido.trabajo_id is not None else None,
            "estado": fila_pedido.estado,
            "creado_en": _iso(fila_pedido.creado_en),
            "total": int(fila_pedido.total),
            "hijos": int(fila_pedido.hijos),
            "colegios": list(fila_pedido.colegios or []),
            "lineas": lineas,
            "pago": _serializar_pago(pago),
            "envio": _serializar_envio(envio, con_celular=con_celular),
        }

    async def pedidos_completos(
        self, filas: list[Any], *, con_celular: bool = False, con_alertas: bool = False
    ) -> list[dict[str, Any]]:
        if not filas:
            return []
        ids = [f.id for f in filas]

        lineas_por_pedido: dict[Any, list[dict[str, Any]]] = {}
        for f in await self.conexion.execute(select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id.in_(ids))):
            lineas_por_pedido.setdefault(f.pedido_id, []).append(_serializar_linea(f))

        pago_por_pedido: dict[Any, Any] = {}
        for f in await self.conexion.execute(
            select(PAGO).where(PAGO.c.pedido_id.in_(ids)).order_by(PAGO.c.creado_en.asc())
        ):
            pago_por_pedido[f.pedido_id] = f

        envio_por_pedido: dict[Any, Any] = {}
        for f in await self.conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id.in_(ids))):
            envio_por_pedido[f.pedido_id] = f

        alertas = await self._alertas_de(filas, pago_por_pedido) if con_alertas else {}

        completos = []
        for f in filas:
            pedido = {
                "pedido_id": str(f.id),
                "usuario_id": str(f.usuario_id),
                "trabajo_id": str(f.trabajo_id) if f.trabajo_id is not None else None,
                "estado": f.estado,
                "creado_en": _iso(f.creado_en),
                "total": int(f.total),
                "hijos": int(f.hijos),
                "colegios": list(f.colegios or []),
                "lineas": lineas_por_pedido.get(f.id, []),
                "pago": _serializar_pago(pago_por_pedido.get(f.id)),
                "envio": _serializar_envio(envio_por_pedido.get(f.id), con_celular=con_celular),
            }
            if con_alertas:
                pedido["alertas"] = list(alertas.get(f.id, ()))
            completos.append(pedido)
        return completos

    async def _alertas_de(
        self, filas: list[Any], pago_por_pedido: dict[Any, Any] | None = None, *, ahora: datetime | None = None
    ) -> dict[Any, tuple[str, ...]]:
        ahora = ahora or datetime.now(UTC)
        candidatas = [
            f
            for f in filas
            if f.estado
            in (EstadoPedido.PAGADO.value, EstadoPedido.PENDIENTE_PAGO.value, EstadoPedido.INCIDENCIA.value)
        ]
        if not candidatas:
            return {}
        ids = [f.id for f in candidatas]
        if pago_por_pedido is None:
            pago_por_pedido = {}
            for p in await self.conexion.execute(
                select(PAGO).where(PAGO.c.pedido_id.in_(ids)).order_by(PAGO.c.creado_en.asc())
            ):
                pago_por_pedido[p.pedido_id] = p
        llegada: dict[Any, tuple[str, datetime]] = {}
        for h in await self.conexion.execute(
            select(HISTORIAL.c.pedido_id, HISTORIAL.c.estado_hacia, HISTORIAL.c.creado_en)
            .where(HISTORIAL.c.pedido_id.in_(ids))
            .order_by(HISTORIAL.c.id.asc())
        ):
            llegada[(h.pedido_id, h.estado_hacia)] = h.creado_en  # type: ignore[index]
        resultado: dict[Any, tuple[str, ...]] = {}
        for f in candidatas:
            pago = pago_por_pedido.get(f.id)
            desde = llegada.get((f.id, f.estado))  # type: ignore[call-overload]
            if desde is None:
                desde = pago.actualizado_en if f.estado == EstadoPedido.PAGADO.value and pago else f.creado_en
            resultado[f.id] = alertas_de_pedido(
                estado=f.estado,
                estado_desde=desde,
                pago_estado=pago.estado if pago else None,
                pago_iniciado_en=pago.creado_en if pago else None,
                creado_en=f.creado_en,
                ahora=ahora,
            )
        return resultado

    async def resumen(self) -> dict[str, Any]:
        por_estado = {e.value: 0 for e in EstadoPedido}
        total_pedidos = 0
        ingresos = 0
        entregas_pendientes = 0

        filas = await self.conexion.execute(
            select(PEDIDO.c.estado, func.count().label("n"), func.sum(PEDIDO.c.total).label("suma")).group_by(
                PEDIDO.c.estado
            )
        )
        for f in filas:
            n = int(f.n)
            suma = int(f.suma or 0)
            por_estado[f.estado] = n
            total_pedidos += n
            if f.estado in _ESTADOS_CONFIRMADOS:
                ingresos += suma
            if f.estado in _ESTADOS_ENTREGA_PENDIENTE:
                entregas_pendientes += n

        candidatas = list(
            await self.conexion.execute(
                select(PEDIDO).where(
                    PEDIDO.c.estado.in_(
                        [EstadoPedido.PAGADO.value, EstadoPedido.PENDIENTE_PAGO.value, EstadoPedido.INCIDENCIA.value]
                    )
                )
            )
        )
        conteo_alertas = dict.fromkeys(ALERTAS, 0)
        for marcas in (await self._alertas_de(candidatas)).values():
            for marca in marcas:
                conteo_alertas[marca] += 1

        return {
            "pedidos_totales": total_pedidos,
            "por_estado": por_estado,
            "ingresos_confirmados": ingresos,
            "entregas_pendientes": entregas_pendientes,
            "alertas": conteo_alertas,
        }

    async def devoluciones_de(self, pedido_id: uuid.UUID, entregado_en: datetime | None) -> list[dict[str, Any]]:
        filas = await self.conexion.execute(
            select(DEVOLUCION).where(DEVOLUCION.c.pedido_id == pedido_id).order_by(DEVOLUCION.c.creado_en.desc())
        )
        return [
            {
                "devolucion_id": str(f.id),
                "motivo": f.motivo,
                "monto": int(f.monto),
                "creado_en": _iso(f.creado_en),
                **evaluar_devolucion(f.creado_en, entregado_en),
            }
            for f in filas
        ]

    async def datos_de_pago_staff(self, pedido_id: uuid.UUID) -> dict[str, Any]:
        fila = (
            await self.conexion.execute(
                select(PAGO.c.transaccion_wompi, PAGO.c.actualizado_en)
                .where(PAGO.c.pedido_id == pedido_id)
                .order_by(PAGO.c.creado_en.desc())
                .limit(1)
            )
        ).one_or_none()
        if fila is None:
            return {"transaccion_wompi": None, "actualizado_en": None}
        return {"transaccion_wompi": fila.transaccion_wompi, "actualizado_en": _iso(fila.actualizado_en)}

    async def listar_todos(self) -> list[Any]:
        return list(await self.conexion.execute(select(PEDIDO).order_by(PEDIDO.c.creado_en.desc())))

    async def listar_de_usuario(self, usuario_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(PEDIDO).where(PEDIDO.c.usuario_id == usuario_id).order_by(PEDIDO.c.creado_en.desc())
            )
        )

    async def obtener(self, pedido_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one_or_none()

    async def pagados_con_trabajo(self) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(PEDIDO.c.trabajo_id, PEDIDO.c.usuario_id, PEDIDO.c.estado).where(
                    PEDIDO.c.estado.in_(_ESTADOS_CONFIRMADOS),
                    PEDIDO.c.trabajo_id.isnot(None),
                )
            )
        )

    async def insertar_orden(
        self,
        *,
        pedido_id: uuid.UUID,
        usuario_id: uuid.UUID,
        trabajo_id: uuid.UUID | None,
        total: int,
        hijos: int,
        colegios: list[str],
        ahora: datetime,
        lineas: list[dict[str, Any]],
        entrega: Any,
    ) -> Any:
        await self.conexion.execute(
            insert(PEDIDO).values(
                id=pedido_id,
                usuario_id=usuario_id,
                trabajo_id=trabajo_id,
                estado=EstadoPedido.PENDIENTE_PAGO.value,
                total=total,
                hijos=hijos,
                colegios=list(colegios),
                creado_en=ahora,
            )
        )
        for linea in lineas:
            await self.conexion.execute(
                insert(LINEA_PEDIDO).values(
                    id=uuid.uuid4(),
                    pedido_id=pedido_id,
                    matricula_id=linea["matricula_id"],
                    producto_canonico_id=linea["producto_id"],
                    sku=linea["sku"],
                    nombre=linea["nombre"],
                    cantidad=linea["cantidad"],
                    precio_unitario=linea["precio_unitario"],
                )
            )
            await self.conexion.execute(
                insert(RESERVA).values(
                    id=uuid.uuid4(),
                    pedido_id=pedido_id,
                    producto_canonico_id=linea["producto_id"],
                    cantidad=linea["cantidad"],
                    estado="activa",
                )
            )
        await self.conexion.execute(
            insert(ENVIO).values(
                id=uuid.uuid4(),
                pedido_id=pedido_id,
                destinatario=entrega.destinatario,
                direccion=entrega.direccion,
                ciudad=entrega.ciudad,
                telefono=getattr(entrega, "telefono", None),
                departamento=getattr(entrega, "departamento", None),
                documento_destinatario=getattr(entrega, "documento_destinatario", None),
                indicaciones=getattr(entrega, "indicaciones", None),
                localidad=getattr(entrega, "localidad", None),
                latitud=getattr(entrega, "latitud", None),
                longitud=getattr(entrega, "longitud", None),
            )
        )
        return (await self.conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one()

    async def contar_pagos_pedido(self, pedido_id: uuid.UUID) -> int:
        return int(
            await self.conexion.scalar(
                select(func.count()).select_from(PAGO).where(PAGO.c.pedido_id == pedido_id)
            )
            or 0
        )

    async def registrar_pago_iniciado(
        self,
        *,
        pago_id: uuid.UUID,
        pedido_id: uuid.UUID,
        referencia_wompi: str,
        transaccion_wompi: str | None,
        metodo: str,
        monto: int,
    ) -> None:
        await self.conexion.execute(
            insert(PAGO).values(
                id=pago_id,
                pedido_id=pedido_id,
                referencia_wompi=referencia_wompi,
                transaccion_wompi=transaccion_wompi,
                metodo=metodo,
                estado=EstadoPago.INICIADO.value,
                monto=monto,
            )
        )

    async def evento_ya_procesado(self, evento_id: str) -> bool:
        ya_visto = await self.conexion.scalar(
            select(EVENTO_PROCESADO.c.id).where(EVENTO_PROCESADO.c.evento_id == evento_id)
        )
        return ya_visto is not None

    async def marcar_evento_procesado(self, evento_id: str) -> None:
        await self.conexion.execute(insert(EVENTO_PROCESADO).values(id=uuid.uuid4(), evento_id=evento_id))

    async def pago_por_referencia(self, referencia: str) -> Any:
        return (
            await self.conexion.execute(select(PAGO).where(PAGO.c.referencia_wompi == referencia))
        ).one_or_none()

    async def actualizar_estado_pago(
        self, *, pago_id: uuid.UUID, estado: str, transaccion_wompi: str | None
    ) -> None:
        await self.conexion.execute(
            update(PAGO)
            .where(PAGO.c.id == pago_id)
            .values(estado=estado, transaccion_wompi=transaccion_wompi)
        )

    async def pedido_de(self, pedido_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one()

    async def transicionar_pedido(self, *, pedido_id: uuid.UUID, destino: str) -> None:
        await self.conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pedido_id).values(estado=destino))

    async def avanzar_despacho(
        self,
        *,
        pedido_id: uuid.UUID,
        desde: str,
        destino: str,
        repartidor_nombre: str | None,
        repartidor_celular: str | None,
        entrega_estimada: datetime | None,
        transportadora: str | None = None,
        guia: str | None = None,
    ) -> bool:
        resultado = await self.conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id == pedido_id, PEDIDO.c.estado == desde).values(estado=destino)
        )
        if resultado.rowcount != 1:
            return False

        cambios: dict[str, Any] = {}
        if repartidor_nombre is not None:
            cambios["repartidor_nombre"] = repartidor_nombre
        if repartidor_celular is not None:
            cambios["repartidor_celular"] = repartidor_celular
        if entrega_estimada is not None:
            cambios["entrega_estimada"] = entrega_estimada
        if transportadora is not None:
            cambios["transportadora"] = transportadora
        if guia is not None:
            cambios["guia"] = guia
        if destino == EstadoPedido.ENTREGADO.value:
            cambios["entregado_en"] = datetime.now(UTC)
        if cambios:
            await self.conexion.execute(update(ENVIO).where(ENVIO.c.pedido_id == pedido_id).values(**cambios))
        return True

    async def registrar_historial(
        self,
        *,
        pedido_id: uuid.UUID,
        estado_desde: str,
        estado_hacia: str,
        actor_id: uuid.UUID,
        nota: str | None,
        tipo_incidencia: str | None,
        actor_correo: str | None = None,
    ) -> None:
        await self.conexion.execute(
            insert(HISTORIAL).values(
                pedido_id=pedido_id,
                estado_desde=estado_desde,
                estado_hacia=estado_hacia,
                actor_id=actor_id,
                actor_correo=actor_correo,
                nota=nota,
                tipo_incidencia=tipo_incidencia,
            )
        )

    async def historial_de(self, pedido_id: uuid.UUID) -> list[dict[str, Any]]:
        filas = await self.conexion.execute(
            select(HISTORIAL).where(HISTORIAL.c.pedido_id == pedido_id).order_by(HISTORIAL.c.id.asc())
        )
        return [_serializar_historial(f) for f in filas]

    async def vistas_para_linea_de_tiempo(
        self, pedido_id: uuid.UUID
    ) -> tuple[list[PagoVisto], list[AvanceVisto], EnvioVisto | None]:
        pagos = [
            PagoVisto(estado=f.estado, actualizado_en=f.actualizado_en)
            for f in await self.conexion.execute(
                select(PAGO.c.estado, PAGO.c.actualizado_en)
                .where(PAGO.c.pedido_id == pedido_id)
                .order_by(PAGO.c.creado_en.asc())
            )
        ]
        historial = [
            AvanceVisto(
                estado_desde=f.estado_desde,
                estado_hacia=f.estado_hacia,
                tipo_incidencia=f.tipo_incidencia,
                creado_en=f.creado_en,
            )
            for f in await self.conexion.execute(
                select(
                    HISTORIAL.c.estado_desde,
                    HISTORIAL.c.estado_hacia,
                    HISTORIAL.c.tipo_incidencia,
                    HISTORIAL.c.creado_en,
                )
                .where(HISTORIAL.c.pedido_id == pedido_id)
                .order_by(HISTORIAL.c.id.asc())
            )
        ]
        envio = (
            await self.conexion.execute(
                select(ENVIO.c.repartidor_nombre, ENVIO.c.entrega_estimada, ENVIO.c.entregado_en).where(
                    ENVIO.c.pedido_id == pedido_id
                )
            )
        ).one_or_none()
        visto = (
            EnvioVisto(
                repartidor_nombre=envio.repartidor_nombre,
                entrega_estimada=envio.entrega_estimada,
                entregado_en=envio.entregado_en,
            )
            if envio
            else None
        )
        return pagos, historial, visto

    async def encolar_aviso_pedido(
        self,
        pedido: Any,
        tipo: str,
        *,
        repartidor: str | None = None,
        reembolso: bool | None = None,
        retoma: bool = False,
    ) -> None:
        carga: dict[str, Any] = {"pedido_id": str(pedido.id), "usuario_id": str(pedido.usuario_id)}
        if repartidor:
            carga["repartidor"] = repartidor
        if reembolso is not None:
            carga["reembolso"] = reembolso
        if retoma:
            carga["retoma"] = True
        await self.conexion.execute(
            insert(BANDEJA).values(
                tipo=tipo,
                agregado_tipo="pedido",
                agregado_id=pedido.id,
                carga=con_correlacion(carga),
            )
        )

    async def encolar_pedido_pagado(self, pedido: Any) -> None:
        await self.conexion.execute(
            insert(BANDEJA).values(
                tipo="pedido_pagado",
                agregado_tipo="pedido",
                agregado_id=pedido.id,
                carga=con_correlacion(
                    {
                        "pedido_id": str(pedido.id),
                        "usuario_id": str(pedido.usuario_id),
                        "total": int(pedido.total),
                    }
                ),
            )
        )

    async def aplicar_resultado(self, datos: EventoPasarela) -> ResultadoAplicacion:
        if await self.evento_ya_procesado(datos.evento_id):
            pago = await self.pago_por_referencia(datos.referencia)
            if pago is None:
                return ResultadoAplicacion("repetido", None, None, None, False)
            pedido = await self.pedido_de(pago.pedido_id)
            return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)
        await self.marcar_evento_procesado(datos.evento_id)

        pago = await self.pago_por_referencia(datos.referencia)
        if pago is None:
            return ResultadoAplicacion("sin_pago", None, None, None, False)

        pedido = await self.pedido_de(pago.pedido_id)

        if pago.estado in ESTADOS_PAGO_FINALES:
            return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)

        if datos.monto_centavos is None or int(datos.monto_centavos) != int(pago.monto) * 100:
            await self.actualizar_estado_pago(
                pago_id=pago.id,
                estado=EstadoPago.RECHAZADO.value,
                transaccion_wompi=datos.transaccion_id or pago.transaccion_wompi,
            )
            return ResultadoAplicacion(
                "monto_no_coincide", pedido.id, EstadoPago.RECHAZADO.value, pedido.estado, False
            )

        if datos.estado == EstadoPago.INICIADO and pago.estado != EstadoPago.INICIADO.value:
            return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)

        valores: dict[str, Any] = {
            "estado": datos.estado.value,
            "transaccion_wompi": datos.transaccion_id or pago.transaccion_wompi,
        }
        if datos.metodo is not None:
            valores["metodo"] = datos.metodo
        await self.conexion.execute(
            update(PAGO)
            .where(PAGO.c.id == pago.id, PAGO.c.estado.notin_(ESTADOS_PAGO_FINALES))
            .values(**valores)
        )

        if datos.estado == EstadoPago.APROBADO and pedido.estado == EstadoPedido.CANCELADO.value:
            await self.conexion.execute(
                insert(BANDEJA).values(
                    tipo="incidencia",
                    agregado_tipo="pedido",
                    agregado_id=pedido.id,
                    carga=con_correlacion(
                        {
                            "pedido_id": str(pedido.id),
                            "usuario_id": str(pedido.usuario_id),
                            "motivo": "pago_tras_cancelacion",
                            "monto": int(pago.monto),
                            "referencia": pago.referencia_wompi,
                        }
                    ),
                )
            )

        destino = pedido_tras_pago(datos.estado, pedido.estado)
        transicionado = False
        pagado = False
        estado_pedido = pedido.estado
        if destino is not None and transicion_valida(pedido.estado, destino):
            await self.transicionar_pedido(pedido_id=pedido.id, destino=destino)
            transicionado = True
            estado_pedido = destino
            if destino == EstadoPedido.PAGADO.value:
                await self.encolar_pedido_pagado(pedido)
                pagado = True
        return ResultadoAplicacion(
            "aplicado", pedido.id, datos.estado.value, estado_pedido, transicionado, pagado
        )

    async def referencias_iniciadas(self, pedido_id: uuid.UUID) -> list[str]:
        return [
            f.referencia_wompi
            for f in await self.conexion.execute(
                select(PAGO.c.referencia_wompi).where(
                    PAGO.c.pedido_id == pedido_id, PAGO.c.estado == EstadoPago.INICIADO.value
                )
            )
        ]

    async def cancelar_pendiente(self, pedido_id: uuid.UUID) -> bool:
        cancelado = await self.conexion.execute(
            update(PEDIDO)
            .where(PEDIDO.c.id == pedido_id, PEDIDO.c.estado == EstadoPedido.PENDIENTE_PAGO.value)
            .values(estado=EstadoPedido.CANCELADO.value)
        )
        if cancelado.rowcount == 0:
            return False
        await self.conexion.execute(
            update(RESERVA)
            .where(RESERVA.c.pedido_id == pedido_id, RESERVA.c.estado == "activa")
            .values(estado="liberada")
        )
        return True

    async def pendientes_del_kit(self, usuario_id: uuid.UUID, trabajo_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(PEDIDO)
                .where(
                    PEDIDO.c.usuario_id == usuario_id,
                    PEDIDO.c.trabajo_id == trabajo_id,
                    PEDIDO.c.estado == EstadoPedido.PENDIENTE_PAGO.value,
                )
                .order_by(PEDIDO.c.creado_en.desc())
            )
        )

    async def contenido_de(
        self, pedido_id: uuid.UUID
    ) -> tuple[list[tuple[str, int, int]], tuple[str | None, ...]]:
        lineas = [
            (f.sku, int(f.cantidad), int(f.precio_unitario))
            for f in await self.conexion.execute(
                select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id == pedido_id)
            )
        ]
        envio = (
            await self.conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == pedido_id))
        ).one_or_none()
        entrega = tuple(getattr(envio, campo) if envio else None for campo in CAMPOS_FIRMA_ENTREGA)
        return lineas, entrega

    async def registrar_devolucion(
        self,
        *,
        devolucion_id: uuid.UUID,
        pedido_id: uuid.UUID,
        usuario_id: uuid.UUID,
        motivo: str,
        monto: int,
    ) -> None:
        await self.conexion.execute(
            insert(DEVOLUCION).values(
                id=devolucion_id,
                pedido_id=pedido_id,
                usuario_id=usuario_id,
                motivo=motivo,
                monto=monto,
            )
        )

    async def devolucion_de(self, pedido_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(DEVOLUCION).where(DEVOLUCION.c.pedido_id == pedido_id).order_by(DEVOLUCION.c.creado_en)
            )
        ).first()

    async def pago_aprobado_en(self, pedido_id: uuid.UUID) -> Any:
        return await self.conexion.scalar(
            select(PAGO.c.actualizado_en)
            .where(
                PAGO.c.pedido_id == pedido_id,
                PAGO.c.estado.in_([EstadoPago.APROBADO.value, EstadoPago.REEMBOLSADO.value]),
            )
            .order_by(PAGO.c.actualizado_en.desc())
            .limit(1)
        )

    async def cancelar_pedido(self, pedido_id: uuid.UUID) -> None:
        await self.conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id == pedido_id).values(estado=EstadoPedido.CANCELADO.value)
        )

    async def marcar_pago_reembolsado(self, pedido_id: uuid.UUID) -> bool:
        resultado = await self.conexion.execute(
            update(PAGO)
            .where(PAGO.c.pedido_id == pedido_id, PAGO.c.estado == EstadoPago.APROBADO.value)
            .values(estado=EstadoPago.REEMBOLSADO.value)
        )
        return bool(resultado.rowcount)
