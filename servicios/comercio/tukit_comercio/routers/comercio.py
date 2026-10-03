"""Las rutas de Comercio: parsear, llamar al dominio, delegar al repo.

Dos superficies, como en el §9 del contrato:

- **Lectura** (`GET /v1/comercio/pedidos`, `/mis-pedidos`, `/{id}`): el tablero
  del back-office de logística y el historial del acudiente. El tablero y el
  detalle son SOLO para staff (operador/admin); "mis pedidos" exige sesión y usa
  el usuario DE LA SESIÓN. Ambas puertas validan el Bearer contra Identidad y
  fallan cerradas (503) si no responde.
- **Escritura** (`POST /v1/ordenes`, `/{id}/pago`, `/v1/webhooks/wompi`,
  `/{id}/retracto`): el checkout. Tres invariantes que no se negocian:
  re-verificar precio antes de cobrar (`422 precio_cambiado`); precio CONGELADO
  en la línea y dirección CONGELADA en el envío (ADR 0012 / 0015); no se guarda
  medio de pago, sólo id de transacción y estado (SG-03). El webhook es
  idempotente contra `evento_pasarela_procesado`.

El router no calcula ni arma SQL: `reverificar_precios`/`total_orden`/
`pedido_tras_pago` viven en `dominio/`, y todo el SQL en `repositorios/`. Aquí
sólo se orquesta y se traducen los resultados a sobres de error.

Los singletons (`pasarela`, `catalogo`, `identidad`, `motor`) se leen de `request.app.state`
en cada petición, no se capturan al importar: así las pruebas pueden sustituir
los dobles después de construir la app.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Header, Request
from pydantic import AwareDatetime, BaseModel, Field
from tukit_comun.http import ErrorDominio
from tukit_comun.metricas import contar_orden_creada, contar_pago_aprobado

from ..dominio.despacho import preparar_avance, validar_avance
from ..dominio.ordenes import LineaResuelta, reverificar_precios, total_orden
from ..dominio.pagos import pedido_tras_pago
from ..modelos import EstadoPago, EstadoPedido, MetodoPago, transicion_valida
from ..remoto import CatalogoCaido, IdentidadCaida
from ..repositorios import RepoPedidos

router = APIRouter(tags=["comercio"])


def _repo(conexion: Any) -> RepoPedidos:
    return RepoPedidos(conexion)


# ---------------------------------------------------------------------------
# Sesion: quien llama. Mismas puertas y mismos sobres que inteligencia
# (`_exigir_staff` / `_usuario_de_sesion`), para que el front trate igual un 401
# de cualquier servicio.
# ---------------------------------------------------------------------------

# Los roles del equipo interno; el admin es superconjunto del operador.
_ROLES_STAFF = frozenset({"admin", "operador"})


def _token_bearer(authorization: str | None) -> str | None:
    """El token del encabezado `Authorization`: `Bearer <token>` o el token pelado."""
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


async def _sesion_valida(request: Request, authorization: str | None) -> dict[str, Any]:
    """La sesion del portador, validada contra Identidad por HTTP (Comercio no
    lee la base de Identidad: regla 1). 401 sin token o con uno invalido; 503 si
    Identidad no responde: FALLA CERRADA, no autorizar por no poder preguntar."""
    token = _token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    try:
        sesion = await request.app.state.identidad.sesion(token)
    except IdentidadCaida as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    return sesion


@dataclass(frozen=True)
class Actor:
    """Quien del equipo interno hace la peticion: lo que queda en el historial."""

    usuario_id: uuid.UUID
    correo: str | None


async def _exigir_staff(request: Request, authorization: str | None) -> Actor:
    """Puerta operador/admin: 401/503 como `_sesion_valida`, 403 si el rol no es
    staff. Devuelve el actor (id y correo de la sesion), que queda en el historial."""
    sesion = await _sesion_valida(request, authorization)
    roles = {r.get("rol") for r in sesion.get("roles", [])}
    if not roles & _ROLES_STAFF:
        raise ErrorDominio(
            "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.", estado=403
        )
    return Actor(usuario_id=uuid.UUID(str(sesion["usuario_id"])), correo=sesion.get("correo"))


async def _usuario_de_sesion(request: Request, authorization: str | None) -> uuid.UUID:
    """Puerta de portador: cualquier sesion valida, sin rol. Devuelve el
    `usuario_id` DE LA SESION, nunca uno que venga del navegador."""
    sesion = await _sesion_valida(request, authorization)
    return uuid.UUID(str(sesion["usuario_id"]))


async def _pedido_o_404(repo: RepoPedidos, pedido_id: uuid.UUID) -> Any:
    fila = await repo.obtener(pedido_id)
    if fila is None:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
    return fila


# ---------------------------------------------------------------------------
# Lectura: tablero de logística e historial del acudiente
# ---------------------------------------------------------------------------


@router.get("/v1/comercio/pedidos", summary="Tablero de logistica: resumen + pedidos")
async def tablero(request: Request, authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Todos los pedidos con la direccion de quien recibe: solo staff. Sin el
    celular del repartidor (eso solo en el detalle)."""
    await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        resumen = await repo.resumen()
        pedidos = await repo.pedidos_completos(await repo.listar_todos())
    return {"resumen": resumen, "pedidos": pedidos}


@router.get("/v1/comercio/mis-pedidos", summary="El historial de pedidos de un acudiente, para su panel.")
async def mis_pedidos(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """Los pedidos del PORTADOR del token, mas recientes primero, para el
    dashboard del padre.

    El `usuario_id` sale de la sesion validada contra Identidad por HTTP, no del
    navegador: antes se aceptaba `?usuario_id=` y cualquiera podia leer los
    pedidos de otro. Si alguien lo sigue mandando, se ignora.
    """
    usuario_id = await _usuario_de_sesion(request, authorization)
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
    por colegio; el navegador nunca lo llama. Va sin token: la puerta la
    responde como ruta inexistente (`RUTAS_BLOQUEADAS` del gateway)."""
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
async def ver_pedido(
    request: Request, pedido_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """El detalle del back-office: solo staff. Es la unica lectura que trae el
    celular del repartidor (para llamarlo) y el historial de avances."""
    await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        return await _detalle_staff(repo, await _pedido_o_404(repo, pedido_id))


async def _detalle_staff(repo: RepoPedidos, fila: Any) -> dict[str, Any]:
    pedido = await repo.pedido_completo(fila, con_celular=True)
    return {**pedido, "historial": await repo.historial_de(fila.id)}


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

    `destino` es el siguiente estado de la cadena de entrega. Con reparto
    propio, el despacho trae nombre y celular del repartidor (y la fecha
    estimada); una incidencia trae su tipo y, si es `otro`, la nota. La validez
    de la transicion y de los datos la decide `validar_avance`: por eso
    `tipo_incidencia` es texto libre y no un `Literal`, para que el rechazo
    llegue con el mensaje del dominio y no como un 400 generico.

    `entrega_estimada` exige zona horaria (`AwareDatetime`): una fecha pelada
    seria medianoche sin zona y se correria al guardarla en `timestamptz`."""

    destino: str = Field(min_length=1, max_length=24)
    repartidor_nombre: str | None = Field(default=None, max_length=128)
    repartidor_celular: str | None = Field(default=None, max_length=32)
    tipo_incidencia: str | None = Field(default=None, max_length=32)
    nota: str | None = Field(default=None, max_length=512)
    entrega_estimada: AwareDatetime | None = None


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
    # Interna (la puerta no la expone): reusa el serializador del pedido, sin el
    # celular del repartidor ni el historial, que son solo del detalle staff.
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        return await repo.pedido_completo(await _pedido_o_404(repo, pedido_id))


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
    "despacho_incompleto": "Para despachar hacen falta el nombre y el celular del repartidor.",
    "incidencia_sin_tipo": "Una incidencia necesita su tipo.",
    "tipo_incidencia_invalido": "Ese tipo de incidencia no existe.",
    "incidencia_sin_nota": "Si la incidencia es 'otro', describe lo ocurrido en la nota.",
}


@router.post("/v1/ordenes/{pedido_id}/avanzar", summary="Avanza un pedido por la cadena de entrega")
async def avanzar_pedido(
    request: Request,
    pedido_id: uuid.UUID,
    solicitud: SolicitudAvance,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Empuja el pedido al siguiente estado de entrega: solo staff.

    Que la transicion sea legal y le toque al back-office, y que vengan los
    datos que el destino exige, lo decide `validar_avance`; un rechazo se
    traduce a su sobre con el codigo y el campo que trae. Si acepta, en UNA
    unidad de trabajo (todo o nada): el cambio de estado guardado contra
    carreras, el sello del envio, la fila de historial con el actor, el aviso
    al acudiente en la bandeja y, al cancelar, el pago marcado para reembolso
    (como el retracto).
    """
    actor = await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await _pedido_o_404(repo, pedido_id)

        entradas = {
            "repartidor_nombre": solicitud.repartidor_nombre,
            "repartidor_celular": solicitud.repartidor_celular,
            "tipo_incidencia": solicitud.tipo_incidencia,
            "nota": solicitud.nota,
        }
        rechazo = validar_avance(pedido.estado, solicitud.destino, **entradas)
        if rechazo is not None:
            raise ErrorDominio(
                rechazo.razon,
                _MENSAJE_AVANCE.get(rechazo.razon, "El avance del pedido no procede."),
                estado=rechazo.estado,
                campo=rechazo.campo,
            )
        avance = preparar_avance(solicitud.destino, **entradas)

        movido = await repo.avanzar_despacho(
            pedido_id=pedido_id,
            desde=pedido.estado,
            destino=solicitud.destino,
            repartidor_nombre=avance.repartidor_nombre,
            repartidor_celular=avance.repartidor_celular,
            entrega_estimada=solicitud.entrega_estimada,
        )
        if not movido:
            # Otro avance gano la carrera entre la lectura y el UPDATE. Lanzar
            # revierte la unidad de trabajo: no queda historial ni aviso huerfano.
            raise ErrorDominio(
                "avance_concurrente",
                "Alguien mas movio este pedido mientras tanto; recarga y vuelve a intentar.",
                estado=409,
            )
        await repo.registrar_historial(
            pedido_id=pedido_id,
            estado_desde=pedido.estado,
            estado_hacia=solicitud.destino,
            actor_id=actor.usuario_id,
            actor_correo=actor.correo,
            nota=avance.nota,
            tipo_incidencia=avance.tipo_incidencia,
        )
        if avance.aviso is not None:
            await repo.encolar_aviso_pedido(pedido, avance.aviso, repartidor=avance.repartidor_nombre)
        if solicitud.destino == EstadoPedido.CANCELADO.value:
            # Como el retracto: el pedido cancelado deja su pago aprobado marcado
            # para reembolso, en la misma transaccion.
            await repo.marcar_pago_reembolsado(pedido_id)

        return await _detalle_staff(repo, await repo.obtener(pedido_id))
