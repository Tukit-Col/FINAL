"""Las rutas de Comercio: parsear, llamar al dominio, delegar al repo.

Dos superficies, como en el §9 del contrato:

- **Lectura** (`GET /v1/comercio/pedidos`, `/mis-pedidos`, `/{id}`): el tablero
  del back-office de logística y el historial del acudiente.
- **Escritura** (`POST /v1/ordenes`, `/{id}/pago`, `/v1/webhooks/wompi`,
  `/{id}/retracto`): el checkout. Tres invariantes que no se negocian:
  re-verificar precio antes de cobrar (`422 precio_cambiado`); precio CONGELADO
  en la línea y dirección CONGELADA en el envío (ADR 0012 / 0015); no se guarda
  medio de pago, sólo id de transacción y estado (SG-03). El webhook es
  idempotente contra `evento_pasarela_procesado`.

El router no calcula ni arma SQL: `reverificar_precios`/`total_orden`/
`pedido_tras_pago` viven en `dominio/`, y todo el SQL en `repositorios/`. Aquí
sólo se orquesta y se traducen los resultados a sobres de error.

Los singletons (`pasarela`, `catalogo`, `motor`) se leen de `request.app.state`
en cada petición, no se capturan al importar: así las pruebas pueden sustituir
los dobles después de construir la app.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from tukit_comun.http import ErrorDominio
from tukit_comun.metricas import contar_orden_creada, contar_pago_aprobado

from ..dominio.despacho import validar_avance
from ..dominio.ordenes import LineaResuelta, reverificar_precios, total_orden
from ..dominio.pagos import pedido_tras_pago
from ..modelos import EstadoPago, EstadoPedido, MetodoPago, transicion_valida
from ..remoto import CatalogoCaido
from ..repositorios import RepoPedidos

router = APIRouter(tags=["comercio"])


def _repo(conexion: Any) -> RepoPedidos:
    return RepoPedidos(conexion)


# ---------------------------------------------------------------------------
# Lectura: tablero de logística e historial del acudiente
# ---------------------------------------------------------------------------


@router.get("/v1/comercio/pedidos", summary="Tablero de logistica: resumen + pedidos")
async def tablero(request: Request) -> dict[str, Any]:
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        resumen = await repo.resumen()
        pedidos = await repo.pedidos_completos(await repo.listar_todos())
    return {"resumen": resumen, "pedidos": pedidos}


@router.get("/v1/comercio/mis-pedidos", summary="El historial de pedidos de un acudiente, para su panel.")
async def mis_pedidos(request: Request, usuario_id: uuid.UUID) -> dict[str, Any]:
    """Los pedidos de UN acudiente, mas recientes primero, para el dashboard del
    padre (que corria sobre datos de muestra por no existir esta superficie).

    Filtra por `usuario_id` y no por el token: verificar el token exigiria
    importar la logica de sesion de Identidad, y eso cruza la frontera (regla 1).
    El id se lo da al frontend `GET /v1/cuenta` de Identidad, que si valida el
    token; aqui Comercio solo devuelve lo de ese id. Es la misma postura que el
    resto de la superficie de lectura, que hoy no exige sesion (ver el gateway).
    """
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedidos = await repo.pedidos_completos(await repo.listar_de_usuario(usuario_id))
    return {"total": len(pedidos), "pedidos": pedidos}


@router.get(
    "/v1/comercio/pedidos-pagados",
    summary="Los pedidos pagados (estado confirmado) con su trabajo, para cruces internos.",
)
async def pedidos_pagados(request: Request) -> dict[str, Any]:
    """El minimo cruce que otro servicio necesita: por cada pedido en un estado
    confirmado y con `trabajo_id`, su `{trabajo_id, usuario_id, estado}`. Nada de
    PII (solo identificadores) y la definicion de "pagado" queda aqui, en
    Comercio, que es su dueno.

    Lo consume Inteligencia server-to-server para armar las metricas de pedidos
    por colegio; el navegador nunca lo llama. Sin token, como el resto de la
    superficie de lectura (ver el gateway y `mis_pedidos`)."""
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        filas = await repo.pagados_con_trabajo()
    return {
        "pedidos": [
            {"trabajo_id": str(f.trabajo_id), "usuario_id": str(f.usuario_id), "estado": f.estado}
            for f in filas
        ]
    }


@router.get("/v1/comercio/pedidos/{pedido_id}", summary="Un pedido, con lineas, pago y envio")
async def ver_pedido(request: Request, pedido_id: uuid.UUID) -> dict[str, Any]:
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        fila = await repo.obtener(pedido_id)
        if fila is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
        return await repo.pedido_completo(fila)


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
    0015): no es una llave a la libreta de Identidad.

    `telefono`/`departamento`/`documento_destinatario`/`indicaciones` son
    opcionales: el checkout legado manda solo los tres primeros y sigue
    cerrando. El formulario nuevo los exige del lado del cliente."""

    destinatario: str = Field(min_length=1, max_length=256)
    direccion: str = Field(min_length=1, max_length=512)
    ciudad: str = Field(min_length=1, max_length=128)
    telefono: str | None = Field(default=None, max_length=32)
    departamento: str | None = Field(default=None, max_length=128)
    documento_destinatario: str | None = Field(default=None, max_length=64)
    indicaciones: str | None = Field(default=None, max_length=512)


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


class SolicitudAvance(BaseModel):
    """Lo que el back-office de logistica manda para avanzar un pedido.

    `destino` es el siguiente estado de la cadena de entrega; transportadora,
    guia y fecha estimada acompañan el despacho y se sellan en el envio. La
    validez de la transicion y de los datos la decide `validar_avance`."""

    destino: str = Field(min_length=1, max_length=24)
    transportadora: str | None = Field(default=None, max_length=128)
    guia: str | None = Field(default=None, max_length=128)
    entrega_estimada: datetime | None = None


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


@router.post("/v1/ordenes", status_code=201, summary="Crea una orden congelando precios")
async def crear_orden(request: Request, solicitud: SolicitudOrden) -> dict[str, Any]:
    """Re-verifica precio contra Catalogo, y solo entonces congela y reserva.

    La primera invariante del §9: antes de cerrar se relee el precio publico de
    cada linea; si cambio respecto al que el acudiente aprobo, la orden NO se
    cierra (`422 precio_cambiado`) y el acudiente decide sobre el precio nuevo.
    Si coincide, se congela en la linea (ADR 0012), se copia la direccion al
    envio (ADR 0015) y se crea la reserva de inventario. Nace `pendiente_pago`.

    La lectura de precios contra Catalogo (I/O de red) ocurre ANTES de abrir la
    sesion de base: nunca se sostiene una conexion de base a traves de una
    llamada HTTP externa.
    """
    usuario_id = _uuid_o_422(solicitud.usuario_id, "usuario_id")
    trabajo_id = _uuid_o_422(solicitud.trabajo_id, "trabajo_id") if solicitud.trabajo_id else None

    # Re-verificacion por HTTP contra Catalogo (no un cruce a su base). Sin
    # poder leer el precio no se cobra: Catalogo caido es 503, no un cobro a
    # ciegas. Cada sku se resuelve a (id canonico, precio vigente) y se arma la
    # linea resuelta que el dominio compara contra el precio aprobado.
    resueltas: list[LineaResuelta] = []
    for linea in solicitud.lineas:
        try:
            resuelto = await request.app.state.catalogo.resolver(linea.sku)
        except CatalogoCaido:
            raise ErrorDominio(
                "catalogo_no_disponible",
                "No se pudo re-verificar el precio con Catalogo; la orden no se cerro.",
                estado=503,
            ) from None
        resueltas.append(
            LineaResuelta(
                sku=linea.sku,
                precio_aprobado=linea.precio_unitario,
                cantidad=linea.cantidad,
                id_canonico=resuelto[0] if resuelto else None,
                precio_actual=resuelto[1] if resuelto else None,
            )
        )

    if reverificar_precios(resueltas):
        raise ErrorDominio(
            "precio_cambiado",
            "El precio de una o mas lineas cambio; revisa el nuevo precio antes de pagar.",
            estado=422,
            campo="lineas",
        )

    # Todos los precios coinciden: se arma la persistencia. El id resuelto por
    # Catalogo manda; si el cliente mando uno se respeta, pero la fuente de
    # verdad es el sku re-verificado arriba.
    por_sku = {r.sku: r for r in resueltas}
    lineas_persistir: list[dict[str, Any]] = []
    for linea in solicitud.lineas:
        id_canonico = por_sku[linea.sku].id_canonico
        producto_id = id_canonico or _uuid_o_422(linea.producto_canonico_id, "producto_canonico_id")
        matricula_id = _uuid_o_422(linea.matricula_id, "matricula_id") if linea.matricula_id else None
        lineas_persistir.append(
            {
                "matricula_id": matricula_id,
                "producto_id": producto_id,
                "sku": linea.sku,
                "nombre": linea.nombre,
                "cantidad": linea.cantidad,
                "precio_unitario": linea.precio_unitario,  # congelado (ADR 0012)
            }
        )

    pedido_id = uuid.uuid4()
    total = total_orden(resueltas)
    ahora = datetime.now(UTC)

    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        fila = await repo.insertar_orden(
            pedido_id=pedido_id,
            usuario_id=usuario_id,
            trabajo_id=trabajo_id,
            total=total,
            hijos=solicitud.hijos,
            colegios=list(solicitud.colegios),
            ahora=ahora,
            lineas=lineas_persistir,
            entrega=solicitud.entrega,
        )
        cuerpo = await repo.pedido_completo(fila)
    # Fuera del `async with`: la orden ya se persistio (commit sin excepcion). La
    # metrica de dominio T1 (ADR 0021) se cuenta aqui para no inflar el numero si
    # la transaccion hubiera hecho rollback.
    contar_orden_creada()
    return cuerpo


@router.post(
    "/v1/ordenes/{pedido_id}/pago",
    status_code=201,
    summary="Inicia el pago con la pasarela (FU-03)",
)
async def iniciar_pago(request: Request, pedido_id: uuid.UUID, solicitud: SolicitudPago) -> dict[str, Any]:
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

    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await repo.obtener(pedido_id)
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
        if pedido.estado != EstadoPedido.PENDIENTE_PAGO.value:
            raise ErrorDominio(
                "pedido_no_pagable",
                "El pedido ya no esta pendiente de pago.",
                estado=409,
            )

        # El intento numera la referencia (`-1`, `-2`, ...): un reintento tras
        # rechazo crea un pago nuevo, y sin el sufijo chocaria con el indice
        # unico de `referencia_wompi`. El webhook la busca por igualdad exacta,
        # asi que numerarla no cambia su lookup.
        intento = await repo.contar_pagos_pedido(pedido_id) + 1
        referencia = f"tukit-{pedido_id}-{intento}"
        try:
            creada = await request.app.state.pasarela.crear_transaccion(
                referencia=referencia,
                monto_centavos=int(pedido.total) * 100,
                correo_cliente=solicitud.correo_cliente,
                metodo=metodo.value,
                url_redireccion=solicitud.url_redireccion,
            )
        except httpx.HTTPError:
            # Wompi caido o devolviendo 5xx: nada se cobro y no se guarda pago.
            # 502, no 500: el fallo es del upstream, y el cliente puede
            # reintentar (la referencia numerada lo permite sin colision).
            raise ErrorDominio(
                "pasarela_no_disponible",
                "No se pudo contactar la pasarela de pago; intenta de nuevo en un momento.",
                estado=502,
            ) from None
        pago_id = uuid.uuid4()
        await repo.registrar_pago_iniciado(
            pago_id=pago_id,
            pedido_id=pedido_id,
            referencia_wompi=creada.referencia,
            transaccion_wompi=creada.transaccion_id,
            metodo=metodo.value,
            monto=int(pedido.total),
        )

    return {
        "pago_id": str(pago_id),
        "referencia_wompi": creada.referencia,
        "transaccion_wompi": creada.transaccion_id,
        "estado": EstadoPago.INICIADO.value,
        "url_redireccion": creada.url_redireccion,
    }


@router.post("/v1/webhooks/wompi", summary="Confirmacion asincrona de la pasarela")
async def webhook_wompi(request: Request, evento: dict[str, Any]) -> dict[str, Any]:
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
    pasarela = request.app.state.pasarela
    if not pasarela.verificar_firma(evento):
        # Firma que no cuadra: se ignora sin mover nada. 200 para que la
        # pasarela no reintente en bucle un evento que nunca vamos a aceptar.
        return {"estado": "ignorado", "motivo": "firma_invalida"}

    datos = pasarela.parsear_evento(evento)
    if not datos.evento_id or not datos.referencia:
        return {"estado": "ignorado", "motivo": "evento_incompleto"}

    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        # Candado de idempotencia: si el evento ya se proceso, no se re-aplica.
        if await repo.evento_ya_procesado(datos.evento_id):
            return {"estado": "repetido", "evento_id": datos.evento_id}
        await repo.marcar_evento_procesado(datos.evento_id)

        pago = await repo.pago_por_referencia(datos.referencia)
        if pago is None:
            # Evento firmado pero de una referencia que no conocemos: se anota
            # como procesado (ya insertado arriba) y no se hace nada mas.
            return {"estado": "sin_pago", "referencia": datos.referencia}

        await repo.actualizar_estado_pago(
            pago_id=pago.id,
            estado=datos.estado.value,
            transaccion_wompi=datos.transaccion_id or pago.transaccion_wompi,
        )

        pedido = await repo.pedido_de(pago.pedido_id)
        destino = pedido_tras_pago(datos.estado, pedido.estado)
        transicionado = False
        pago_aprobado = False
        if destino is not None and transicion_valida(pedido.estado, destino):
            await repo.transicionar_pedido(pedido_id=pedido.id, destino=destino)
            transicionado = True
            if destino == EstadoPedido.PAGADO.value:
                # Outbox: el aviso sale de aqui, misma transaccion que el pago.
                await repo.encolar_pedido_pagado(pedido)
                pago_aprobado = True

    # Fuera del `async with`: se conto solo si el pago llevo el pedido a PAGADO y
    # la transaccion cerro bien (T3 de la saga, ADR 0021). El candado de
    # idempotencia arriba evita contar dos veces un webhook repetido.
    if pago_aprobado:
        contar_pago_aprobado()

    return {
        "estado": "aplicado",
        "evento_id": datos.evento_id,
        "pago_estado": datos.estado.value,
        "pedido_transicionado": transicionado,
    }


@router.get("/v1/ordenes/{pedido_id}", summary="Seguimiento de una orden (FU-01 + UM-03)")
async def ver_orden(request: Request, pedido_id: uuid.UUID) -> dict[str, Any]:
    # El seguimiento reusa el serializador del pedido: la misma forma que la
    # lectura de logistica, ahora del lado del acudiente.
    return await ver_pedido(request, pedido_id)


@router.post("/v1/ordenes/{pedido_id}/retracto", status_code=201, summary="Retracto o devolucion (FU-04)")
async def retractar_orden(
    request: Request, pedido_id: uuid.UUID, solicitud: SolicitudRetracto
) -> dict[str, Any]:
    """Registra la devolucion, cancela el pedido si la transicion lo permite y
    marca el pago para reembolso. El monto del reembolso es el total pagado."""
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await repo.obtener(pedido_id)
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)

        cancelable = transicion_valida(pedido.estado, EstadoPedido.CANCELADO.value)
        devolucion_id = uuid.uuid4()
        await repo.registrar_devolucion(
            devolucion_id=devolucion_id,
            pedido_id=pedido_id,
            usuario_id=pedido.usuario_id,
            motivo=solicitud.motivo,
            monto=int(pedido.total),
        )
        if cancelable:
            await repo.cancelar_pedido(pedido_id)
            await repo.marcar_pago_reembolsado(pedido_id)

    return {
        "devolucion_id": str(devolucion_id),
        "pedido_id": str(pedido_id),
        "cancelado": cancelable,
        "estado": EstadoPedido.CANCELADO.value if cancelable else pedido.estado,
    }


_MENSAJE_AVANCE = {
    "destino_invalido": "El estado destino no es uno de los del pedido.",
    "transicion_invalida": "No se puede pasar el pedido a ese estado desde el actual.",
    "despacho_incompleto": "Un despacho necesita transportadora y guia para poder rastrearse.",
}


@router.post("/v1/ordenes/{pedido_id}/avanzar", summary="Avanza un pedido por la cadena de entrega")
async def avanzar_pedido(
    request: Request, pedido_id: uuid.UUID, solicitud: SolicitudAvance
) -> dict[str, Any]:
    """Empuja el pedido al siguiente estado de entrega y sella el envio.

    La legalidad de la transicion la decide la tabla (`transicion_valida`, via
    `validar_avance`); la unica regla extra —despachar exige transportadora y
    guia— tambien. Si el dominio rechaza, se traduce a su sobre de error con el
    codigo que trae. Si acepta, la transicion y el sello del envio se guardan en
    la misma unidad de trabajo.
    """
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await repo.obtener(pedido_id)
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)

        rechazo = validar_avance(
            pedido.estado,
            solicitud.destino,
            transportadora=solicitud.transportadora,
            guia=solicitud.guia,
        )
        if rechazo is not None:
            raise ErrorDominio(
                rechazo.razon,
                _MENSAJE_AVANCE.get(rechazo.razon, "El avance del pedido no procede."),
                estado=rechazo.estado,
                campo="destino",
            )

        await repo.avanzar_despacho(
            pedido_id=pedido_id,
            destino=solicitud.destino,
            transportadora=solicitud.transportadora,
            guia=solicitud.guia,
            entrega_estimada=solicitud.entrega_estimada,
        )
        fila = await repo.obtener(pedido_id)
        return await repo.pedido_completo(fila)
