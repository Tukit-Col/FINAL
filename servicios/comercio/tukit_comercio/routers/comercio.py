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
from sqlalchemy.exc import IntegrityError
from tukit_comun.http import ErrorDominio
from tukit_comun.metricas import contar_orden_creada, contar_pago_aprobado

from ..dominio.despacho import validar_avance
from ..dominio.ordenes import LineaResuelta, reverificar_precios, total_orden
from ..dominio.pagos import firma_orden, vencido
from ..modelos import EstadoPago, EstadoPedido, MetodoPago, transicion_valida
from ..pasarela import EventoPasarela, PasarelaCaida, TransaccionNoExiste
from ..remoto import CatalogoCaido
from ..repositorios import RepoPedidos
from ..repositorios.pedidos import ResultadoAplicacion

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

    # Un kit, un pedido pendiente. Si el acudiente vuelve a pulsar Pagar con lo
    # mismo, se reutiliza el pedido (Inteligencia le crea un intento de pago
    # nuevo); si cambio algo, el pendiente anterior se cancela, pero solo si
    # Wompi confirma que no tiene un pago aprobado o en curso.
    if trabajo_id is not None:
        reutilizable = await _resolver_pendientes_del_kit(request, usuario_id, trabajo_id, solicitud)
        if reutilizable is not None:
            return reutilizable

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
        if vencido(pedido.creado_en):
            raise ErrorDominio(
                "pedido_vencido",
                "Este pedido tiene mas de 24 horas. Vuelve a armar tu kit para ver el precio de hoy.",
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
        "widget": creada.widget,
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
    if not datos.evento_id or not datos.referencia or not datos.transaccion_id:
        return {"estado": "ignorado", "motivo": "evento_incompleto"}

    async with request.app.state.motor.sesion() as db:
        resultado = await _repo(await db.connection()).aplicar_resultado(datos)

    # Fuera del `async with`: se conto solo si el pago llevo el pedido a PAGADO y
    # la transaccion cerro bien (T3 de la saga, ADR 0021). El candado de
    # idempotencia evita contar dos veces un webhook repetido.
    if resultado.pagado:
        contar_pago_aprobado()

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


@router.post(
    "/v1/pagos/{transaccion_id}/sincronizar",
    summary="Sincroniza el pago con la pasarela al regreso del acudiente",
)
async def sincronizar_pago(request: Request, transaccion_id: str) -> dict[str, Any]:
    """Consulta la transaccion en la pasarela y la aplica como lo hace el webhook.

    El acudiente vuelve del checkout alojado con el id de la transaccion en la
    URL; aqui se le pregunta a la pasarela su estado real (no se confia en lo que
    traiga el navegador) y se aplica con el mismo aplicador idempotente del
    webhook, asi que sincronizar y recibir el webhook no se pisan ni duplican el
    aviso.
    """
    try:
        datos = await request.app.state.pasarela.consultar_transaccion(transaccion_id)
    except TransaccionNoExiste:
        raise ErrorDominio(
            "transaccion_no_existe", "La pasarela no conoce esa transaccion", estado=404
        ) from None
    except PasarelaCaida:
        raise ErrorDominio(
            "pasarela_no_disponible", "No se pudo consultar la pasarela de pagos", estado=502
        ) from None

    resultado = await _aplicar_con_reintento(request, datos)
    if resultado.estado == "sin_pago" or resultado.pedido_id is None:
        raise ErrorDominio("pago_no_existe", "No hay un pago para esa transaccion", estado=404)
    async with request.app.state.motor.sesion() as db:
        pedido = await _repo(await db.connection()).pedido_de(resultado.pedido_id)
    return {
        "pedido_id": str(resultado.pedido_id),
        "total": int(pedido.total),
        "estado_pago": resultado.estado_pago,
        "estado_pedido": resultado.estado_pedido,
        "trabajo_id": str(pedido.trabajo_id) if pedido.trabajo_id is not None else None,
    }


async def _aplicar_con_reintento(request: Request, datos: EventoPasarela) -> ResultadoAplicacion:
    """Aplica un resultado en su propia sesion. Si el webhook llega a la vez, el
    segundo INSERT del candado choca con el indice unico: se reintenta UNA vez
    en una sesion nueva, donde la fila ya existe y el resultado es `repetido`."""
    for intento in range(2):
        try:
            async with request.app.state.motor.sesion() as db:
                resultado = await _repo(await db.connection()).aplicar_resultado(datos)
            if resultado.pagado:
                contar_pago_aprobado()
            return resultado
        except IntegrityError:
            if intento == 1:
                raise
    raise AssertionError("inalcanzable")


async def _revisar_pagos_en_wompi(request: Request, pedido_id: uuid.UUID) -> str:
    """Antes de cancelar: `pagado`, `en_curso` o `libre`.

    Un PSE puede estar en curso, o ya aprobado, sin que Tukit lo sepa (el
    acudiente no volvio y no hay webhook). Se busca en Wompi cada intento que
    aqui sigue `iniciado`; uno aprobado se aplica en el acto (el pedido pasa a
    `pagado`) y uno rechazado se anota. Si Wompi no responde, `PasarelaCaida`
    sube: sin saberlo no se cancela.
    """
    async with request.app.state.motor.sesion() as db:
        referencias = await _repo(await db.connection()).referencias_iniciadas(pedido_id)
    en_curso = False
    for referencia in referencias:
        evento = await request.app.state.pasarela.consultar_por_referencia(referencia)
        if evento is None:
            continue
        if evento.estado == EstadoPago.INICIADO:
            en_curso = True
            continue
        resultado = await _aplicar_con_reintento(request, evento)
        if resultado.estado_pedido == EstadoPedido.PAGADO.value:
            return "pagado"
    return "en_curso" if en_curso else "libre"


async def _cancelar_si_se_puede(request: Request, pedido_id: uuid.UUID) -> str:
    """Cancela un pedido pendiente y libera su reserva, si Wompi lo permite.

    Devuelve `cancelado`, `pagado`, `en_curso` o `no_cancelable`.
    """
    async with request.app.state.motor.sesion() as db:
        pedido = await _repo(await db.connection()).obtener(pedido_id)
    if pedido is None or pedido.estado != EstadoPedido.PENDIENTE_PAGO.value:
        return "no_cancelable"
    revision = await _revisar_pagos_en_wompi(request, pedido_id)
    if revision != "libre":
        return revision
    async with request.app.state.motor.sesion() as db:
        cancelado = await _repo(await db.connection()).cancelar_pendiente(pedido_id)
    return "cancelado" if cancelado else "no_cancelable"


async def _resolver_pendientes_del_kit(
    request: Request, usuario_id: uuid.UUID, trabajo_id: uuid.UUID, solicitud: SolicitudOrden
) -> dict[str, Any] | None:
    """El pedido pendiente a reutilizar para este kit, o `None` para crear uno.

    Uno identico y vigente se reutiliza. Los demas pendientes del mismo kit se
    cancelan con la revision de Wompi; uno con pago en curso o aprobado se deja
    como esta (cancelarlo podria cobrar sin entregar), y si Wompi no responde
    tambien se deja: duplicar es mejor que cancelar a ciegas.
    """
    buscada = firma_orden(
        [(linea.sku, linea.cantidad, linea.precio_unitario) for linea in solicitud.lineas],
        (solicitud.entrega.destinatario, solicitud.entrega.direccion, solicitud.entrega.ciudad),
    )
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pendientes = await repo.pendientes_del_kit(usuario_id, trabajo_id)
        for pedido in pendientes:
            if vencido(pedido.creado_en):
                continue
            lineas, entrega = await repo.contenido_de(pedido.id)
            if firma_orden(lineas, entrega) == buscada:
                return await repo.pedido_completo(pedido)

    for pedido in pendientes:
        try:
            await _cancelar_si_se_puede(request, pedido.id)
        except PasarelaCaida:
            continue
    return None


@router.post(
    "/v1/ordenes/{pedido_id}/cancelar",
    summary="Cancela un pedido pendiente de pago, si Wompi no tiene un pago en curso",
)
async def cancelar_orden(request: Request, pedido_id: uuid.UUID) -> dict[str, Any]:
    """El acudiente cancela un pedido que no pago. Antes se le pregunta a Wompi
    por cada intento: cancelar con un PSE aprobado o en curso cobraria sin
    entregar. Cancelado, la reserva de inventario se libera."""
    async with request.app.state.motor.sesion() as db:
        existe = await _repo(await db.connection()).obtener(pedido_id)
    if existe is None:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
    try:
        resultado = await _cancelar_si_se_puede(request, pedido_id)
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
    return await ver_pedido(request, pedido_id)


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
