"""La superficie de Comercio: lectura de logistica y escritura de checkout.

Dos superficies, como en el diseno del §9 del contrato:

- **Lectura** (`GET /v1/comercio/pedidos`, `/{id}`): el tablero del back-office
  de logistica (`libs/ts/tukit-contrato/src/comercio.ts`). `TableroComercio
  {resumen, pedidos[]}`, cada `Pedido` con sus lineas, su pago (o null) y su
  envio (o null). El `resumen` se calcula con agregados sobre la misma base
  para que la tarjeta de arriba no recuente en cada pantalla.
- **Escritura** (`POST /v1/ordenes`, `/{id}/pago`, `/v1/webhooks/wompi`,
  `/{id}/retracto`): el checkout del acudiente. Tres invariantes del §9 que no
  se negocian: re-verificar precio y disponibilidad antes de cobrar (si
  cambiaron, `422 precio_cambiado`); el precio queda CONGELADO en la linea al
  confirmar (ADR 0012) y la direccion CONGELADA en el envio (ADR 0015); y no se
  guarda medio de pago, solo id de transaccion y estado (SG-03). El webhook es
  idempotente contra `evento_pasarela_procesado`.

    python -m tukit_comercio.api            # localhost:8014
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app
from tukit_comun.http import iso as _iso

from .modelos import Base, EstadoPago, EstadoPedido, MetodoPago, transicion_valida
from .pasarela import EventoPasarela, PasarelaCaida, TransaccionNoExiste, pasarela_desde_entorno
from .remoto import CatalogoCaido, ClienteCatalogo

PUERTO_POR_OMISION = 8014

# Cuanto tiempo se puede pagar un pedido pendiente. Despues se cobraria un
# precio congelado viejo: el acudiente vuelve a armar el kit y el precio se
# re-verifica contra Catalogo. No hay columna nueva: sale de `creado_en`.
VIGENCIA_PAGO = timedelta(hours=24)

PEDIDO = Base.metadata.tables["pedido"]
LINEA_PEDIDO = Base.metadata.tables["linea_pedido"]
PAGO = Base.metadata.tables["pago"]
ENVIO = Base.metadata.tables["envio"]
DEVOLUCION = Base.metadata.tables["devolucion"]
RESERVA = Base.metadata.tables["reserva_inventario"]
EVENTO_PROCESADO = Base.metadata.tables["evento_pasarela_procesado"]
BANDEJA = Base.metadata.tables["bandeja_salida"]

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


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("comercio")
    # La pasarela y el cliente de Catalogo se cuelgan de la app para poder
    # sustituirlos por dobles en las pruebas sin tocar los endpoints. La
    # pasarela sale de WOMPI_MODO (falso por omision, sandbox con llaves).
    app.state.pasarela = pasarela_desde_entorno()
    app.state.catalogo = ClienteCatalogo()


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Comercio",
    descripcion=(
        "Pedidos, inventario, pagos (Wompi PSE) y entrega. Superficie de lectura del "
        "back-office de logistica y superficie de checkout del acudiente."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
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


def _serializar_envio(fila: Any) -> dict[str, Any] | None:
    if fila is None:
        return None
    return {
        "destinatario": fila.destinatario,
        "direccion": fila.direccion,
        "ciudad": fila.ciudad,
        "transportadora": fila.transportadora,
        "guia": fila.guia,
        "entrega_estimada": _iso(fila.entrega_estimada),
        "entregado_en": _iso(fila.entregado_en),
    }


def _serializar_linea(fila: Any) -> dict[str, Any]:
    return {
        "sku": fila.sku,
        "nombre": fila.nombre,
        "cantidad": int(fila.cantidad),
        "precio_unitario": int(fila.precio_unitario),
    }


async def _pedido_completo(conexion: Any, fila_pedido: Any) -> dict[str, Any]:
    """Un `Pedido` del contrato: con sus lineas, su pago y su envio anidados.

    Toma la fila del pedido ya leida para no repetir la consulta cuando viene
    del listado. El pago que se muestra es el ultimo intento; el envio es uno a
    uno con el pedido.
    """
    lineas = [
        _serializar_linea(f)
        for f in await conexion.execute(
            select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id == fila_pedido.id)
        )
    ]
    pago = (
        await conexion.execute(
            select(PAGO).where(PAGO.c.pedido_id == fila_pedido.id).order_by(PAGO.c.creado_en.desc()).limit(1)
        )
    ).one_or_none()
    envio = (await conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == fila_pedido.id))).one_or_none()

    return {
        "pedido_id": str(fila_pedido.id),
        "trabajo_id": str(fila_pedido.trabajo_id) if fila_pedido.trabajo_id is not None else None,
        "estado": fila_pedido.estado,
        "creado_en": _iso(fila_pedido.creado_en),
        "total": int(fila_pedido.total),
        "hijos": int(fila_pedido.hijos),
        "colegios": list(fila_pedido.colegios or []),
        "lineas": lineas,
        "pago": _serializar_pago(pago),
        "envio": _serializar_envio(envio),
    }


async def _pedidos_completos(conexion: Any, filas: list[Any]) -> list[dict[str, Any]]:
    """Varios pedidos anidados en 3 consultas, no 3 por pedido.

    El listado hacia N+1: `_pedido_completo` corre una consulta de lineas, una de
    pago y una de envio POR pedido, asi que un tablero de 200 pedidos disparaba
    ~600 idas a la base. Aqui se cargan las lineas, los pagos y los envios de
    TODOS los pedidos de una con `WHERE pedido_id IN (...)` y se agrupan en
    memoria. El pago que se muestra sigue siendo el ultimo intento (se ordena por
    fecha y el ultimo por pedido gana). El camino de un solo pedido sigue usando
    `_pedido_completo`, que ahi no tiene el problema.
    """
    if not filas:
        return []
    ids = [f.id for f in filas]

    lineas_por_pedido: dict[Any, list[dict[str, Any]]] = {}
    for f in await conexion.execute(select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id.in_(ids))):
        lineas_por_pedido.setdefault(f.pedido_id, []).append(_serializar_linea(f))

    # El ultimo intento de pago por pedido: se ordena por fecha y el ultimo que
    # se ve por pedido (el mas reciente) sobrescribe.
    pago_por_pedido: dict[Any, Any] = {}
    for f in await conexion.execute(
        select(PAGO).where(PAGO.c.pedido_id.in_(ids)).order_by(PAGO.c.creado_en.asc())
    ):
        pago_por_pedido[f.pedido_id] = f

    envio_por_pedido: dict[Any, Any] = {}
    for f in await conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id.in_(ids))):
        envio_por_pedido[f.pedido_id] = f

    return [
        {
            "pedido_id": str(f.id),
            "trabajo_id": str(f.trabajo_id) if f.trabajo_id is not None else None,
            "estado": f.estado,
            "creado_en": _iso(f.creado_en),
            "total": int(f.total),
            "hijos": int(f.hijos),
            "colegios": list(f.colegios or []),
            "lineas": lineas_por_pedido.get(f.id, []),
            "pago": _serializar_pago(pago_por_pedido.get(f.id)),
            "envio": _serializar_envio(envio_por_pedido.get(f.id)),
        }
        for f in filas
    ]


async def _resumen(conexion: Any) -> dict[str, Any]:
    """El consolidado que pinta las tarjetas de arriba sin recontar por pantalla."""
    por_estado = {e.value: 0 for e in EstadoPedido}
    total_pedidos = 0
    ingresos = 0
    entregas_pendientes = 0

    filas = await conexion.execute(
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


@app.get("/v1/comercio/pedidos", tags=["comercio"], summary="Tablero de logistica: resumen + pedidos")
async def tablero() -> dict[str, Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        resumen = await _resumen(conexion)
        filas = list(await conexion.execute(select(PEDIDO).order_by(PEDIDO.c.creado_en.desc())))
        pedidos = await _pedidos_completos(conexion, filas)
    return {"resumen": resumen, "pedidos": pedidos}


@app.get(
    "/v1/comercio/mis-pedidos",
    tags=["comercio"],
    summary="El historial de pedidos de un acudiente, para su panel.",
)
async def mis_pedidos(usuario_id: uuid.UUID) -> dict[str, Any]:
    """Los pedidos de UN acudiente, mas recientes primero, para el dashboard del
    padre (que corria sobre datos de muestra por no existir esta superficie).

    Filtra por `usuario_id` y no por el token: verificar el token exigiria
    importar la logica de sesion de Identidad, y eso cruza la frontera (regla 1).
    El id se lo da al frontend `GET /v1/cuenta` de Identidad, que si valida el
    token; aqui Comercio solo devuelve lo de ese id. Es la misma postura que el
    resto de la superficie de lectura, que hoy no exige sesion (ver el gateway).
    """
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        filas = list(
            await conexion.execute(
                select(PEDIDO).where(PEDIDO.c.usuario_id == usuario_id).order_by(PEDIDO.c.creado_en.desc())
            )
        )
        pedidos = await _pedidos_completos(conexion, filas)
    return {"total": len(pedidos), "pedidos": pedidos}


@app.get(
    "/v1/comercio/pedidos-pagados",
    tags=["comercio"],
    summary="Los pedidos pagados (estado confirmado) con su trabajo, para cruces internos.",
)
async def pedidos_pagados() -> dict[str, Any]:
    """El minimo cruce que otro servicio necesita: por cada pedido en un estado
    de `_ESTADOS_CONFIRMADOS` y con `trabajo_id`, su `{trabajo_id, usuario_id,
    estado}`. Nada de PII (solo identificadores) y la definicion de "pagado"
    queda aqui, en Comercio, que es su dueno.

    Lo consume Inteligencia server-to-server para armar las metricas de pedidos
    por colegio; el navegador nunca lo llama. Sin token, como el resto de la
    superficie de lectura (ver el gateway y `mis_pedidos`)."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        filas = list(
            await conexion.execute(
                select(PEDIDO.c.trabajo_id, PEDIDO.c.usuario_id, PEDIDO.c.estado).where(
                    PEDIDO.c.estado.in_(_ESTADOS_CONFIRMADOS),
                    PEDIDO.c.trabajo_id.isnot(None),
                )
            )
        )
    return {
        "pedidos": [
            {
                "trabajo_id": str(f.trabajo_id),
                "usuario_id": str(f.usuario_id),
                "estado": f.estado,
            }
            for f in filas
        ]
    }


@app.get("/v1/comercio/pedidos/{pedido_id}", tags=["comercio"], summary="Un pedido, con lineas, pago y envio")
async def ver_pedido(pedido_id: uuid.UUID) -> dict[str, Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        fila = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one_or_none()
        if fila is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
        return await _pedido_completo(conexion, fila)


# ---------------------------------------------------------------------------
# Escritura: checkout, pago y webhook (§9 del contrato)
# ---------------------------------------------------------------------------


class LineaOrden(BaseModel):
    """Un renglon que el acudiente aprobo. El precio que trae es el que VIO;
    Comercio lo re-verifica contra Catalogo y solo lo congela si sigue igual."""

    # Opcional: Comercio lo resuelve por sku contra Catalogo (endpoint interno),
    # en la misma lectura con que re-verifica el precio. Quien arma la orden
    # (Inteligencia, el navegador) nunca ve un id canonico -RPO cero, ADR 0017-,
    # asi que no puede mandarlo; se acepta si viene, pero no se exige.
    producto_canonico_id: str | None = None
    sku: str = Field(min_length=1, max_length=64)
    nombre: str = Field(min_length=1, max_length=256)
    cantidad: int = Field(gt=0)
    precio_unitario: int = Field(ge=0)
    matricula_id: str | None = None


class DireccionEntrega(BaseModel):
    """La direccion a la que se entrega. Se COPIA congelada en el envio (ADR
    0015): no es una llave a la libreta de Identidad."""

    destinatario: str = Field(min_length=1, max_length=256)
    direccion: str = Field(min_length=1, max_length=512)
    ciudad: str = Field(min_length=1, max_length=128)


class SolicitudOrden(BaseModel):
    """Lo que el checkout manda para crear una orden (FU-01)."""

    usuario_id: str
    trabajo_id: str | None = None
    hijos: int = Field(default=0, ge=0)
    colegios: list[str] = Field(default_factory=list)
    lineas: list[LineaOrden] = Field(min_length=1)
    entrega: DireccionEntrega


class SolicitudPago(BaseModel):
    """Lo que el checkout manda para iniciar el pago (FU-03)."""

    correo_cliente: str = Field(min_length=5, max_length=320)
    metodo: str = Field(default=MetodoPago.PSE.value, max_length=16)
    url_redireccion: str | None = None


class SolicitudRetracto(BaseModel):
    """Lo que el checkout manda para un retracto o devolucion (FU-04)."""

    motivo: str = Field(default="", max_length=512)


def _uuid_o_422(valor: str, campo: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorDominio(
            "identificador_invalido",
            f"El campo {campo} no tiene forma de identificador.",
            estado=422,
            campo=campo,
        ) from None


@app.post("/v1/ordenes", tags=["comercio"], status_code=201, summary="Crea una orden congelando precios")
async def crear_orden(solicitud: SolicitudOrden) -> dict[str, Any]:
    """Re-verifica precio contra Catalogo, y solo entonces congela y reserva.

    La primera invariante del §9: antes de cerrar se relee el precio publico de
    cada linea; si cambio respecto al que el acudiente aprobo, la orden NO se
    cierra (`422 precio_cambiado`) y el acudiente decide sobre el precio nuevo.
    Si coincide, se congela en la linea (ADR 0012), se copia la direccion al
    envio (ADR 0015) y se crea la reserva de inventario. Nace `pendiente_pago`.
    """
    usuario_id = _uuid_o_422(solicitud.usuario_id, "usuario_id")
    trabajo_id = _uuid_o_422(solicitud.trabajo_id, "trabajo_id") if solicitud.trabajo_id else None

    # Re-verificacion por HTTP contra Catalogo (no un cruce a su base). Sin
    # poder leer el precio no se cobra: Catalogo caido es 503, no un cobro a
    # ciegas.
    cambios: list[dict[str, Any]] = []
    # sku -> id canonico resuelto por Catalogo, para congelar linea y reserva
    # sin que quien arma la orden tenga que conocer el id (RPO cero, ADR 0017).
    ids: dict[str, uuid.UUID] = {}
    for linea in solicitud.lineas:
        try:
            resuelto = await app.state.catalogo.resolver(linea.sku)
        except CatalogoCaido:
            raise ErrorDominio(
                "catalogo_no_disponible",
                "No se pudo re-verificar el precio con Catalogo; la orden no se cerro.",
                estado=503,
            ) from None
        precio_actual = resuelto[1] if resuelto else None
        if resuelto is None or precio_actual is None or precio_actual != linea.precio_unitario:
            cambios.append(
                {"sku": linea.sku, "precio_aprobado": linea.precio_unitario, "precio_actual": precio_actual}
            )
        else:
            ids[linea.sku] = resuelto[0]

    if cambios:
        raise ErrorDominio(
            "precio_cambiado",
            "El precio de una o mas lineas cambio; revisa el nuevo precio antes de pagar.",
            estado=422,
            campo="lineas",
        )

    # Un kit, un pedido pendiente. Si el acudiente vuelve a pulsar Pagar con lo
    # mismo, se reutiliza el pedido (Inteligencia le crea un intento de pago
    # nuevo); si cambio algo, el pendiente anterior se cancela, pero solo si
    # Wompi confirma que no tiene un pago aprobado o en curso.
    if trabajo_id is not None:
        reutilizable = await _resolver_pendientes_del_kit(usuario_id, trabajo_id, solicitud)
        if reutilizable is not None:
            return reutilizable

    pedido_id = uuid.uuid4()
    total = sum(linea.precio_unitario * linea.cantidad for linea in solicitud.lineas)
    ahora = datetime.now(UTC)

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(PEDIDO).values(
                id=pedido_id,
                usuario_id=usuario_id,
                trabajo_id=trabajo_id,
                estado=EstadoPedido.PENDIENTE_PAGO.value,
                total=total,
                hijos=solicitud.hijos,
                colegios=list(solicitud.colegios),
                creado_en=ahora,
            )
        )
        for linea in solicitud.lineas:
            # El id resuelto por Catalogo manda; si el cliente mando uno se
            # respeta, pero la fuente de verdad es el sku re-verificado arriba.
            producto_id = ids.get(linea.sku) or _uuid_o_422(linea.producto_canonico_id, "producto_canonico_id")
            matricula_id = _uuid_o_422(linea.matricula_id, "matricula_id") if linea.matricula_id else None
            await conexion.execute(
                insert(LINEA_PEDIDO).values(
                    id=uuid.uuid4(),
                    pedido_id=pedido_id,
                    matricula_id=matricula_id,
                    producto_canonico_id=producto_id,
                    sku=linea.sku,
                    nombre=linea.nombre,
                    cantidad=linea.cantidad,
                    precio_unitario=linea.precio_unitario,  # congelado (ADR 0012)
                )
            )
            await conexion.execute(
                insert(RESERVA).values(
                    id=uuid.uuid4(),
                    pedido_id=pedido_id,
                    producto_canonico_id=producto_id,
                    cantidad=linea.cantidad,
                    estado="activa",
                )
            )
        # Direccion congelada al envio (ADR 0015): copia, no llave.
        await conexion.execute(
            insert(ENVIO).values(
                id=uuid.uuid4(),
                pedido_id=pedido_id,
                destinatario=solicitud.entrega.destinatario,
                direccion=solicitud.entrega.direccion,
                ciudad=solicitud.entrega.ciudad,
            )
        )
        fila = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one()
        return await _pedido_completo(conexion, fila)


@app.post(
    "/v1/ordenes/{pedido_id}/pago",
    tags=["comercio"],
    status_code=201,
    summary="Inicia el pago con la pasarela (FU-03)",
)
async def iniciar_pago(pedido_id: uuid.UUID, solicitud: SolicitudPago) -> dict[str, Any]:
    """Crea la transaccion en la pasarela y guarda solo id + estado (SG-03).

    El medio de pago viaja a Wompi y no se persiste. `referencia_wompi` es el
    ancla por la que el webhook encontrara este pago mas tarde.
    """
    try:
        metodo = MetodoPago(solicitud.metodo)
    except ValueError:
        raise ErrorDominio(
            "metodo_invalido",
            "El medio de pago no es uno de los aceptados.",
            estado=422,
            campo="metodo",
        ) from None

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        pedido = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one_or_none()
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
        if pedido.estado != EstadoPedido.PENDIENTE_PAGO.value:
            raise ErrorDominio(
                "pedido_no_pagable",
                "El pedido ya no esta pendiente de pago.",
                estado=409,
            )
        if _vencido(pedido.creado_en):
            raise ErrorDominio(
                "pedido_vencido",
                "Este pedido tiene mas de 24 horas. Vuelve a armar tu kit para ver el precio de hoy.",
                estado=409,
            )

        # Una referencia por intento: Wompi no admite repetirla, y un pago
        # rechazado deja reintentar el mismo pedido.
        pago_id = uuid.uuid4()
        referencia = f"tukit-{pago_id}"
        creada = await app.state.pasarela.crear_transaccion(
            referencia=referencia,
            monto_centavos=int(pedido.total) * 100,
            correo_cliente=solicitud.correo_cliente,
            metodo=metodo.value,
            url_redireccion=solicitud.url_redireccion,
        )
        await conexion.execute(
            insert(PAGO).values(
                id=pago_id,
                pedido_id=pedido_id,
                referencia_wompi=creada.referencia,
                transaccion_wompi=creada.transaccion_id,
                metodo=metodo.value,
                estado=EstadoPago.INICIADO.value,
                monto=int(pedido.total),
            )
        )

    return {
        "pago_id": str(pago_id),
        "referencia_wompi": creada.referencia,
        "transaccion_wompi": creada.transaccion_id,
        "estado": EstadoPago.INICIADO.value,
        "url_redireccion": creada.url_redireccion,
        "widget": creada.widget,
    }


def _pedido_tras_pago(estado_pago: EstadoPago, estado_actual: str) -> str | None:
    """El estado al que pasa el pedido segun el resultado del pago.

    Aprobado lleva `pendiente_pago -> pagado`; rechazado lo deja donde estaba
    (el acudiente puede reintentar). Devuelve `None` cuando no hay que mover
    nada, y el llamador respeta las transiciones validas del dominio.
    """
    if estado_pago == EstadoPago.APROBADO:
        return EstadoPedido.PAGADO.value
    return None


_ESTADOS_PAGO_FINALES = (EstadoPago.APROBADO.value, EstadoPago.REEMBOLSADO.value)


@dataclass(frozen=True)
class ResultadoAplicacion:
    """Lo que dejo la aplicacion de un resultado de pago.

    `estado`: `aplicado`, `repetido`, `sin_pago` o `monto_no_coincide`. Los demas
    campos reflejan el pago y el pedido tal como quedaron (None si no hay pago).
    """

    estado: str
    pedido_id: uuid.UUID | None
    estado_pago: str | None
    estado_pedido: str | None
    transicionado: bool


async def _aplicar_resultado(conexion: Any, datos: EventoPasarela) -> ResultadoAplicacion:
    """Aplica una sola vez el resultado de un pago, llegue por webhook o por sync.

    Candado de idempotencia: `evento_pasarela_procesado`. El SELECT previo cubre
    el reintento en serie sin envenenar la transaccion; el indice unico de la
    columna es el respaldo duro contra dos entregas simultaneas. Valida que el
    monto reportado sea el del pago (un monto distinto rechaza el pago y no mueve
    el pedido). En la primera aplicacion de un pago aprobado, transiciona el
    pedido a `pagado` y escribe `pedido_pagado` en la bandeja de salida DENTRO de
    la misma transaccion (patron outbox).
    """
    ya_visto = await conexion.scalar(
        select(EVENTO_PROCESADO.c.id).where(EVENTO_PROCESADO.c.evento_id == datos.evento_id)
    )
    if ya_visto is not None:
        pago = (
            await conexion.execute(select(PAGO).where(PAGO.c.referencia_wompi == datos.referencia))
        ).one_or_none()
        if pago is None:
            return ResultadoAplicacion("repetido", None, None, None, False)
        pedido = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pago.pedido_id))).one()
        return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)
    await conexion.execute(insert(EVENTO_PROCESADO).values(id=uuid.uuid4(), evento_id=datos.evento_id))

    pago = (
        await conexion.execute(select(PAGO).where(PAGO.c.referencia_wompi == datos.referencia))
    ).one_or_none()
    if pago is None:
        # Evento de una referencia que no conocemos: queda anotado como
        # procesado (ya insertado arriba) y no se hace nada mas.
        return ResultadoAplicacion("sin_pago", None, None, None, False)

    pedido = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pago.pedido_id))).one()

    if pago.estado in _ESTADOS_PAGO_FINALES:
        # Un pago ya aprobado/reembolsado no retrocede: un evento tardio o fuera
        # de orden (PENDING despues de APPROVED, p. ej.) queda anotado y no cambia nada.
        return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)

    if datos.monto_centavos is None or int(datos.monto_centavos) != int(pago.monto) * 100:
        await conexion.execute(
            update(PAGO)
            .where(PAGO.c.id == pago.id)
            .values(
                estado=EstadoPago.RECHAZADO.value,
                transaccion_wompi=datos.transaccion_id or pago.transaccion_wompi,
            )
        )
        return ResultadoAplicacion(
            "monto_no_coincide", pedido.id, EstadoPago.RECHAZADO.value, pedido.estado, False
        )

    if datos.estado == EstadoPago.INICIADO and pago.estado != EstadoPago.INICIADO.value:
        # Un PENDING tardio no revive un pago ya rechazado: se anota y no cambia nada.
        return ResultadoAplicacion("repetido", pedido.id, pago.estado, pedido.estado, False)

    valores: dict[str, Any] = {
        "estado": datos.estado.value,
        "transaccion_wompi": datos.transaccion_id or pago.transaccion_wompi,
    }
    if datos.metodo is not None:
        valores["metodo"] = datos.metodo
    # El `notin_` cierra la carrera: si otro escritor dejo el pago en un estado
    # final entre la lectura y esta escritura, no se le pisa.
    await conexion.execute(
        update(PAGO)
        .where(PAGO.c.id == pago.id, PAGO.c.estado.notin_(_ESTADOS_PAGO_FINALES))
        .values(**valores)
    )

    if datos.estado == EstadoPago.APROBADO and pedido.estado == EstadoPedido.CANCELADO.value:
        # Red de seguridad: el pedido se cancelo mientras un pago seguia en curso
        # y Wompi lo aprobo. `cancelado` es terminal, asi que el pedido no se
        # mueve, pero el cobro no puede perderse en silencio: se deja una
        # incidencia (el repartidor la avisa al acudiente) y operacion la ve en
        # el tablero como pedido cancelado con pago aprobado.
        await conexion.execute(
            insert(BANDEJA).values(
                tipo="incidencia",
                agregado_tipo="pedido",
                agregado_id=pedido.id,
                carga={
                    "pedido_id": str(pedido.id),
                    "usuario_id": str(pedido.usuario_id),
                    "motivo": "pago_tras_cancelacion",
                    "monto": int(pago.monto),
                    "referencia": pago.referencia_wompi,
                },
            )
        )

    destino = _pedido_tras_pago(datos.estado, pedido.estado)
    transicionado = False
    estado_pedido = pedido.estado
    if destino is not None and transicion_valida(pedido.estado, destino):
        await conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pedido.id).values(estado=destino))
        transicionado = True
        estado_pedido = destino
        if destino == EstadoPedido.PAGADO.value:
            # Outbox: el aviso sale de aqui, misma transaccion que el pago.
            await conexion.execute(
                insert(BANDEJA).values(
                    tipo="pedido_pagado",
                    agregado_tipo="pedido",
                    agregado_id=pedido.id,
                    carga={
                        "pedido_id": str(pedido.id),
                        "usuario_id": str(pedido.usuario_id),
                        "total": int(pedido.total),
                    },
                )
            )
    return ResultadoAplicacion("aplicado", pedido.id, datos.estado.value, estado_pedido, transicionado)


@app.post("/v1/webhooks/wompi", tags=["comercio"], summary="Confirmacion asincrona de la pasarela")
async def webhook_wompi(evento: dict[str, Any]) -> dict[str, Any]:
    """Aplica el resultado del pago una sola vez, aunque Wompi reintente.

    Verifica la firma (un evento que no la trae valida se ignora), y usa
    `evento_pasarela_procesado` como candado de idempotencia. En el flujo normal
    (Wompi reintenta en serie) un SELECT previo detecta el evento ya visto y se
    responde 200 sin re-aplicar; la insercion en la misma transaccion, con su
    indice unico, es el respaldo duro contra dos entregas simultaneas. En la
    primera aplicacion de un pago aprobado, transiciona el pedido a `pagado` y
    escribe `pedido_pagado` en la bandeja de salida DENTRO de la misma
    transaccion (patron outbox): el aviso al acudiente y el cambio de estado se
    guardan juntos o no se guardan.
    """
    if not app.state.pasarela.verificar_firma(evento):
        # Firma que no cuadra: se ignora sin mover nada. 200 para que la
        # pasarela no reintente en bucle un evento que nunca vamos a aceptar.
        return {"estado": "ignorado", "motivo": "firma_invalida"}

    datos = app.state.pasarela.parsear_evento(evento)
    if not datos.evento_id or not datos.referencia or not datos.transaccion_id:
        return {"estado": "ignorado", "motivo": "evento_incompleto"}

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        resultado = await _aplicar_resultado(conexion, datos)

    if resultado.estado == "repetido":
        return {"estado": "repetido", "evento_id": datos.evento_id}
    if resultado.estado == "sin_pago":
        return {"estado": "sin_pago", "referencia": datos.referencia}
    if resultado.estado == "monto_no_coincide":
        return {"estado": "monto_no_coincide", "evento_id": datos.evento_id}
    return {
        "estado": "aplicado",
        "evento_id": datos.evento_id,
        "pago_estado": datos.estado.value,
        "pedido_transicionado": resultado.transicionado,
    }


@app.post(
    "/v1/pagos/{transaccion_id}/sincronizar",
    tags=["comercio"],
    summary="Sincroniza el pago con la pasarela al regreso del acudiente",
)
async def sincronizar_pago(transaccion_id: str) -> dict[str, Any]:
    """Consulta la transaccion en la pasarela y la aplica como lo hace el webhook.

    El acudiente vuelve del checkout alojado con el id de la transaccion en la
    URL; aqui se le pregunta a la pasarela su estado real (no se confia en lo que
    traiga el navegador) y se aplica con el mismo aplicador idempotente del
    webhook, asi que sincronizar y recibir el webhook no se pisan ni duplican el
    aviso. Si el webhook llega a la vez, el segundo INSERT del candado choca con
    el indice unico: se reintenta UNA vez en una sesion nueva, donde la fila ya
    existe y el resultado es `repetido` con el estado vigente.
    """
    try:
        datos = await app.state.pasarela.consultar_transaccion(transaccion_id)
    except TransaccionNoExiste:
        raise ErrorDominio(
            "transaccion_no_existe", "La pasarela no conoce esa transaccion", estado=404
        ) from None
    except PasarelaCaida:
        raise ErrorDominio(
            "pasarela_no_disponible", "No se pudo consultar la pasarela de pagos", estado=502
        ) from None

    resultado = await _aplicar_con_reintento(datos)
    if resultado.estado == "sin_pago" or resultado.pedido_id is None:
        raise ErrorDominio("pago_no_existe", "No hay un pago para esa transaccion", estado=404)
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        consulta = select(PEDIDO.c.total, PEDIDO.c.trabajo_id).where(PEDIDO.c.id == resultado.pedido_id)
        fila = (await conexion.execute(consulta)).one()
    total = int(fila.total)
    trabajo_id = str(fila.trabajo_id) if fila.trabajo_id is not None else None
    return {
        "pedido_id": str(resultado.pedido_id),
        "total": total,
        "estado_pago": resultado.estado_pago,
        "estado_pedido": resultado.estado_pedido,
        "trabajo_id": trabajo_id,
    }


async def _aplicar_con_reintento(datos: EventoPasarela) -> ResultadoAplicacion:
    """Aplica un resultado en su propia sesion. Si el webhook llega a la vez, el
    segundo INSERT del candado choca con el indice unico: se reintenta UNA vez
    en una sesion nueva, donde la fila ya existe y el resultado es `repetido`."""
    for intento in range(2):
        try:
            async with app.state.motor.sesion() as db:
                conexion = await db.connection()
                return await _aplicar_resultado(conexion, datos)
        except IntegrityError:
            if intento == 1:
                raise
    raise AssertionError("inalcanzable")


def _vencido(creado_en: datetime) -> bool:
    """Si el pedido ya paso su ventana de pago. SQLite devuelve fechas sin zona:
    se leen como UTC, que es como se escribieron."""
    if creado_en.tzinfo is None:
        creado_en = creado_en.replace(tzinfo=UTC)
    return datetime.now(UTC) - creado_en > VIGENCIA_PAGO


async def _revisar_pagos_en_wompi(pedido_id: uuid.UUID) -> str:
    """Antes de cancelar: `pagado`, `en_curso` o `libre`.

    Un PSE puede estar en curso, o ya aprobado, sin que Tukit lo sepa (el
    acudiente no volvio y no hay webhook). Se busca en Wompi cada intento que
    aqui sigue `iniciado`; uno aprobado se aplica en el acto (el pedido pasa a
    `pagado`) y uno rechazado se anota. Si Wompi no responde, `PasarelaCaida`
    sube: sin saberlo no se cancela.
    """
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        referencias = [
            f.referencia_wompi
            for f in await conexion.execute(
                select(PAGO.c.referencia_wompi).where(
                    PAGO.c.pedido_id == pedido_id, PAGO.c.estado == EstadoPago.INICIADO.value
                )
            )
        ]
    en_curso = False
    for referencia in referencias:
        evento = await app.state.pasarela.consultar_por_referencia(referencia)
        if evento is None:
            continue
        if evento.estado == EstadoPago.INICIADO:
            en_curso = True
            continue
        resultado = await _aplicar_con_reintento(evento)
        if resultado.estado_pedido == EstadoPedido.PAGADO.value:
            return "pagado"
    return "en_curso" if en_curso else "libre"


async def _cancelar_si_se_puede(pedido_id: uuid.UUID) -> str:
    """Cancela un pedido pendiente y libera su reserva, si Wompi lo permite.

    Devuelve `cancelado`, `pagado`, `en_curso` o `no_cancelable`. La escritura
    vuelve a exigir `pendiente_pago`: si un pago se aplico entre la revision y
    este UPDATE, el pedido no se toca.
    """
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        estado = await conexion.scalar(select(PEDIDO.c.estado).where(PEDIDO.c.id == pedido_id))
    if estado != EstadoPedido.PENDIENTE_PAGO.value:
        return "no_cancelable"
    revision = await _revisar_pagos_en_wompi(pedido_id)
    if revision != "libre":
        return revision
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        cancelado = await conexion.execute(
            update(PEDIDO)
            .where(PEDIDO.c.id == pedido_id, PEDIDO.c.estado == EstadoPedido.PENDIENTE_PAGO.value)
            .values(estado=EstadoPedido.CANCELADO.value)
        )
        if cancelado.rowcount == 0:
            return "no_cancelable"
        await conexion.execute(
            update(RESERVA)
            .where(RESERVA.c.pedido_id == pedido_id, RESERVA.c.estado == "activa")
            .values(estado="liberada")
        )
    return "cancelado"


def _firma_orden(lineas: list[tuple[str, int, int]], entrega: tuple[str, str, str]) -> tuple[Any, ...]:
    """Lo que hace "la misma orden": productos (sin importar el orden) y entrega."""
    return (tuple(sorted(lineas)), entrega)


async def _resolver_pendientes_del_kit(
    usuario_id: uuid.UUID, trabajo_id: uuid.UUID, solicitud: SolicitudOrden
) -> dict[str, Any] | None:
    """El pedido pendiente a reutilizar para este kit, o `None` para crear uno.

    Uno identico y vigente se reutiliza. Los demas pendientes del mismo kit se
    cancelan con la revision de Wompi; uno con pago en curso o aprobado se deja
    como esta (cancelarlo podria cobrar sin entregar), y si Wompi no responde
    tambien se deja: duplicar es mejor que cancelar a ciegas.
    """
    buscada = _firma_orden(
        [(linea.sku, linea.cantidad, linea.precio_unitario) for linea in solicitud.lineas],
        (solicitud.entrega.destinatario, solicitud.entrega.direccion, solicitud.entrega.ciudad),
    )
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        pendientes = list(
            await conexion.execute(
                select(PEDIDO)
                .where(
                    PEDIDO.c.usuario_id == usuario_id,
                    PEDIDO.c.trabajo_id == trabajo_id,
                    PEDIDO.c.estado == EstadoPedido.PENDIENTE_PAGO.value,
                )
                .order_by(PEDIDO.c.creado_en.desc())
            )
        )
        for pedido in pendientes:
            if _vencido(pedido.creado_en):
                continue
            lineas = [
                (f.sku, int(f.cantidad), int(f.precio_unitario))
                for f in await conexion.execute(
                    select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id == pedido.id)
                )
            ]
            envio = (
                await conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == pedido.id))
            ).one_or_none()
            entrega = (envio.destinatario, envio.direccion, envio.ciudad) if envio else ("", "", "")
            if _firma_orden(lineas, entrega) == buscada:
                return await _pedido_completo(conexion, pedido)

    for pedido in pendientes:
        try:
            await _cancelar_si_se_puede(pedido.id)
        except PasarelaCaida:
            continue
    return None


@app.post(
    "/v1/ordenes/{pedido_id}/cancelar",
    tags=["comercio"],
    summary="Cancela un pedido pendiente de pago, si Wompi no tiene un pago en curso",
)
async def cancelar_orden(pedido_id: uuid.UUID) -> dict[str, Any]:
    """El acudiente cancela un pedido que no pago. Antes se le pregunta a Wompi
    por cada intento: cancelar con un PSE aprobado o en curso cobraria sin
    entregar. Cancelado, la reserva de inventario se libera."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        existe = await conexion.scalar(select(PEDIDO.c.id).where(PEDIDO.c.id == pedido_id))
    if existe is None:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
    try:
        resultado = await _cancelar_si_se_puede(pedido_id)
    except PasarelaCaida:
        raise ErrorDominio(
            "pasarela_no_disponible",
            "No pudimos confirmar con Wompi que no tengas un pago en curso. Intenta en unos minutos.",
            estado=502,
        ) from None
    if resultado == "pagado":
        raise ErrorDominio(
            "pedido_ya_pagado",
            "Tu pago de este pedido ya fue aprobado, asi que no lo cancelamos.",
            estado=409,
        )
    if resultado == "en_curso":
        raise ErrorDominio(
            "pago_en_curso",
            "Tu pago todavia se esta procesando. Espera la respuesta de tu banco antes de cancelar.",
            estado=409,
        )
    if resultado == "no_cancelable":
        raise ErrorDominio(
            "pedido_no_cancelable", "Solo se pueden cancelar pedidos pendientes de pago.", estado=409
        )
    return await ver_pedido(pedido_id)


@app.get("/v1/ordenes/{pedido_id}", tags=["comercio"], summary="Seguimiento de una orden (FU-01 + UM-03)")
async def ver_orden(pedido_id: uuid.UUID) -> dict[str, Any]:
    # El seguimiento reusa el serializador del pedido: la misma forma que la
    # lectura de logistica, ahora del lado del acudiente.
    return await ver_pedido(pedido_id)


@app.post(
    "/v1/ordenes/{pedido_id}/retracto",
    tags=["comercio"],
    status_code=201,
    summary="Retracto o devolucion de una orden (FU-04)",
)
async def retractar_orden(pedido_id: uuid.UUID, solicitud: SolicitudRetracto) -> dict[str, Any]:
    """Registra la devolucion, cancela el pedido si la transicion lo permite y
    marca el pago para reembolso. El monto del reembolso es el total pagado."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        pedido = (await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))).one_or_none()
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)

        cancelable = transicion_valida(pedido.estado, EstadoPedido.CANCELADO.value)
        devolucion_id = uuid.uuid4()
        await conexion.execute(
            insert(DEVOLUCION).values(
                id=devolucion_id,
                pedido_id=pedido_id,
                usuario_id=pedido.usuario_id,
                motivo=solicitud.motivo,
                monto=int(pedido.total),
            )
        )
        if cancelable:
            await conexion.execute(
                update(PEDIDO).where(PEDIDO.c.id == pedido_id).values(estado=EstadoPedido.CANCELADO.value)
            )
            # El reembolso lo lleva el pago, no la devolucion.
            await conexion.execute(
                update(PAGO)
                .where(PAGO.c.pedido_id == pedido_id, PAGO.c.estado == EstadoPago.APROBADO.value)
                .values(estado=EstadoPago.REEMBOLSADO.value)
            )

    return {
        "devolucion_id": str(devolucion_id),
        "pedido_id": str(pedido_id),
        "cancelado": cancelable,
        "estado": EstadoPedido.CANCELADO.value if cancelable else pedido.estado,
    }


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Comercio.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
