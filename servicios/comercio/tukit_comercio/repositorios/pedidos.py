"""El SQL de Comercio contra su propia base, detrás de nombres de método.

Todo lo que aquí vive salió, verbatim, de los manejadores de `api.py`: los
`insert` del checkout, las lecturas del tablero, los serializadores de
proyección y la secuencia idempotente del webhook. El router abre la sesión y
la unidad de trabajo (`async with motor.sesion()`), construye un `RepoPedidos`
atado a esa conexión y le pide cada paso; el repo no decide nada de negocio
—eso es de `dominio/`— ni conoce HTTP.

Los estados que cuentan como ingreso o como entrega pendiente son clasificación
de negocio, pero se usan sólo dentro de la agregación del resumen y se quedan
junto a ella para no partir dos `frozenset` en un módulo aparte.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, insert, select, update
from tukit_comun.bandeja import con_correlacion
from tukit_comun.http import iso as _iso

from ..modelos import Base, EstadoPago, EstadoPedido

PEDIDO = Base.metadata.tables["pedido"]
LINEA_PEDIDO = Base.metadata.tables["linea_pedido"]
PAGO = Base.metadata.tables["pago"]
ENVIO = Base.metadata.tables["envio"]
DEVOLUCION = Base.metadata.tables["devolucion"]
RESERVA = Base.metadata.tables["reserva_inventario"]
EVENTO_PROCESADO = Base.metadata.tables["evento_pasarela_procesado"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
HISTORIAL = Base.metadata.tables["historial_pedido"]

# Los estados que cuentan como ingreso confirmado: ya se pago, aunque todavia
# no se entregue. `entregado` incluido; `cancelado` e `incidencia` no.
_ESTADOS_CONFIRMADOS = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
        EstadoPedido.ENTREGADO.value,
    }
)

# Un pedido pagado que todavia no llega es una entrega pendiente. `entregado`
# ya llego; los previos al pago aun no cuentan.
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
    """El envio del contrato. El celular del repartidor es dato personal de un
    tercero que solo necesita el staff para llamarlo: sale unicamente con
    `con_celular` (el detalle del back-office), nunca en listados ni al acudiente."""
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


class RepoPedidos:
    """El repositorio de pedidos, atado a una conexión de una unidad de trabajo.

    Se construye dentro del `async with motor.sesion()` del router, con la
    conexión ya abierta; sus métodos son las consultas que antes vivían sueltas
    en los manejadores. No abre ni cierra la sesión: eso es del router.
    """

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    # -- lectura -----------------------------------------------------------

    async def pedido_completo(self, fila_pedido: Any, *, con_celular: bool = False) -> dict[str, Any]:
        """Un `Pedido` del contrato: con sus lineas, su pago y su envio anidados.

        Toma la fila del pedido ya leida para no repetir la consulta cuando viene
        del listado. El pago que se muestra es el ultimo intento; el envio es uno a
        uno con el pedido.
        """
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
            # El dueño del pedido: el back-office lo usa para mostrar su correo
            # (que vive en Identidad); en "mis pedidos" es el propio portador.
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

    async def pedidos_completos(self, filas: list[Any], *, con_celular: bool = False) -> list[dict[str, Any]]:
        """Varios pedidos anidados en 3 consultas, no 3 por pedido.

        El listado hacia N+1: `pedido_completo` corre una consulta de lineas, una de
        pago y una de envio POR pedido, asi que un tablero de 200 pedidos disparaba
        ~600 idas a la base. Aqui se cargan las lineas, los pagos y los envios de
        TODOS los pedidos de una con `WHERE pedido_id IN (...)` y se agrupan en
        memoria. El pago que se muestra sigue siendo el ultimo intento (se ordena por
        fecha y el ultimo por pedido gana). El camino de un solo pedido sigue usando
        `pedido_completo`, que ahi no tiene el problema.
        """
        if not filas:
            return []
        ids = [f.id for f in filas]

        lineas_por_pedido: dict[Any, list[dict[str, Any]]] = {}
        for f in await self.conexion.execute(select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id.in_(ids))):
            lineas_por_pedido.setdefault(f.pedido_id, []).append(_serializar_linea(f))

        # El ultimo intento de pago por pedido: se ordena por fecha y el ultimo que
        # se ve por pedido (el mas reciente) sobrescribe.
        pago_por_pedido: dict[Any, Any] = {}
        for f in await self.conexion.execute(
            select(PAGO).where(PAGO.c.pedido_id.in_(ids)).order_by(PAGO.c.creado_en.asc())
        ):
            pago_por_pedido[f.pedido_id] = f

        envio_por_pedido: dict[Any, Any] = {}
        for f in await self.conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id.in_(ids))):
            envio_por_pedido[f.pedido_id] = f

        return [
            {
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
            for f in filas
        ]

    async def resumen(self) -> dict[str, Any]:
        """El consolidado que pinta las tarjetas de arriba sin recontar por pantalla."""
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

        return {
            "pedidos_totales": total_pedidos,
            "por_estado": por_estado,
            "ingresos_confirmados": ingresos,
            "entregas_pendientes": entregas_pendientes,
        }

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
        """Los pedidos en un estado confirmado (`_ESTADOS_CONFIRMADOS`) que tienen
        `trabajo_id`: el cruce minimo que otro servicio necesita, sin PII."""
        return list(
            await self.conexion.execute(
                select(PEDIDO.c.trabajo_id, PEDIDO.c.usuario_id, PEDIDO.c.estado).where(
                    PEDIDO.c.estado.in_(_ESTADOS_CONFIRMADOS),
                    PEDIDO.c.trabajo_id.isnot(None),
                )
            )
        )

    # -- escritura: checkout ----------------------------------------------

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
        """Los 4 inserts del checkout, en la misma transacción: pedido, líneas,
        reservas y envío. Devuelve la fila del pedido re-leída.

        `lineas` viene ya resuelta por el router: cada dict trae el
        `producto_id` canónico (resuelto contra Catálogo o validado del cliente)
        y el `matricula_id` ya parseado. El precio queda CONGELADO (ADR 0012) y
        la dirección se COPIA al envío (ADR 0015).
        """
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
                    precio_unitario=linea["precio_unitario"],  # congelado (ADR 0012)
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
        # Direccion congelada al envio (ADR 0015): copia, no llave. Los cuatro
        # campos extendidos viajan por `getattr` con `None` por defecto para que
        # cualquier objeto de entrega (el legado o el nuevo) sirva sin ramas.
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
            )
        )
        return (await self.conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one()

    # -- escritura: pago ---------------------------------------------------

    async def contar_pagos_pedido(self, pedido_id: uuid.UUID) -> int:
        """Cuantos intentos de pago tiene ya el pedido.

        El siguiente intento es `contar + 1`: es lo que hace unica la
        `referencia_wompi` de un reintento tras rechazo, que si no chocaria con
        el indice unico y reventaria el segundo pago con un 500.
        """
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

    # -- escritura: webhook ------------------------------------------------

    async def evento_ya_procesado(self, evento_id: str) -> bool:
        """El candado de idempotencia: si el evento ya se vio, no se re-aplica.

        El SELECT cubre el reintento en serie sin envenenar la transaccion; el
        indice unico de la columna es el respaldo duro contra dos entregas
        simultaneas.
        """
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
    ) -> bool:
        """Avanza el estado del pedido y, en el mismo paso, sella el envio.

        El `UPDATE` exige que el pedido SIGA en `desde`, el estado que el router
        leyo y valido. Si dos operadores mueven el mismo pedido a la vez, el
        segundo no encuentra la fila (Postgres re-evalua el WHERE tras el commit
        del primero) y recibe `False`: sin esa guarda pisaria un estado que no
        valido. Con `False` no se toca el envio y el router responde 409.

        Los datos de despacho (repartidor, fecha estimada) son parte del hecho y
        se graban en el `Envio` cuando llegan; `entregado_en` se marca al llegar
        a `entregado`. Todo va en la unidad de trabajo del router.
        """
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
        """Una fila por avance, en la misma transaccion que el cambio de estado."""
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
        """Los avances del pedido en el orden en que ocurrieron (el `id` creciente)."""
        filas = await self.conexion.execute(
            select(HISTORIAL).where(HISTORIAL.c.pedido_id == pedido_id).order_by(HISTORIAL.c.id.asc())
        )
        return [_serializar_historial(f) for f in filas]

    async def encolar_aviso_pedido(self, pedido: Any, tipo: str, *, repartidor: str | None = None) -> None:
        """Outbox: el aviso al acudiente de un avance, en la MISMA transaccion.

        La carga lleva lo minimo para avisar: a quien (`usuario_id`) y de que
        pedido. El nombre del repartidor viaja porque el texto lo dice ("va con
        Luis"); el celular, la nota y el tipo de incidencia NO: el broker publica
        la fila entera y Operacion guarda la carga como datos de la notificacion.
        """
        carga: dict[str, Any] = {"pedido_id": str(pedido.id), "usuario_id": str(pedido.usuario_id)}
        if repartidor:
            carga["repartidor"] = repartidor
        await self.conexion.execute(
            insert(BANDEJA).values(
                tipo=tipo,
                agregado_tipo="pedido",
                agregado_id=pedido.id,
                carga=con_correlacion(carga),
            )
        )

    async def encolar_pedido_pagado(self, pedido: Any) -> None:
        """Outbox: el aviso `pedido_pagado` sale en la MISMA transacción que el
        cambio de estado del pedido. El cambio y el aviso se guardan juntos o no
        se guardan (patrón outbox, §9)."""
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

    # -- escritura: retracto ----------------------------------------------

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

    async def cancelar_pedido(self, pedido_id: uuid.UUID) -> None:
        await self.conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id == pedido_id).values(estado=EstadoPedido.CANCELADO.value)
        )

    async def marcar_pago_reembolsado(self, pedido_id: uuid.UUID) -> None:
        """El reembolso lo lleva el pago aprobado del pedido, no la devolución."""
        await self.conexion.execute(
            update(PAGO)
            .where(PAGO.c.pedido_id == pedido_id, PAGO.c.estado == EstadoPago.APROBADO.value)
            .values(estado=EstadoPago.REEMBOLSADO.value)
        )
